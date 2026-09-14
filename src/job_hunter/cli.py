from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from job_hunter import db
from job_hunter.cv_parser import extract_text
from job_hunter.graph import build_graph
from job_hunter.nodes.score import DEFAULT_MAX_CANDIDATES_TO_SCORE
from job_hunter.notify import filter_new_strong_matches, send_digest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CV_PATH = REPO_ROOT / "config" / "CV.pdf"
DEFAULT_PREFERENCES_PATH = REPO_ROOT / "config" / "preferences.yaml"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "jobs.db"


def run(
    *,
    cv_path: Path = DEFAULT_CV_PATH,
    preferences_path: Path = DEFAULT_PREFERENCES_PATH,
    db_path: Path = DEFAULT_DB_PATH,
    min_strong_matches: int = 5,
    max_iterations: int = 2,
    max_candidates_to_score: int = DEFAULT_MAX_CANDIDATES_TO_SCORE,
    notify: bool = True,
    on_node_complete: Callable[[str], None] | None = None,
    llm: Any = None,
    http_client: Any = None,
) -> list:
    cv_text = extract_text(cv_path)
    preferences = yaml.safe_load(preferences_path.read_text()) or {}

    initial_state = {
        "cv_text": cv_text,
        "preferences": preferences,
        "min_strong_matches": min_strong_matches,
        "max_iterations": max_iterations,
        "max_candidates_to_score": max_candidates_to_score,
        "llm": llm,
        "http_client": http_client,
    }

    app = build_graph()
    if on_node_complete is None:
        final_state = app.invoke(initial_state)
    else:
        # Plain-overwrite merge matches how every node in this graph behaves
        # (each returns full replacement values for its own keys, no
        # accumulating reducers), so this mirrors invoke()'s result exactly
        # while giving the caller a callback per completed node.
        final_state = dict(initial_state)
        for update in app.stream(initial_state, stream_mode="updates"):
            for node_name, delta in update.items():
                final_state.update(delta)
                on_node_complete(node_name)

    jobs = final_state["candidates"]

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = db.get_connection(db_path)
    try:
        previously_seen_ids = {row["job_id"] for row in conn.execute("SELECT job_id FROM jobs")}
        db.upsert_jobs(conn, jobs)
    finally:
        conn.close()

    if notify:
        # send_digest no-ops safely if Resend isn't configured yet, so this
        # never fails a run just because notification setup is incomplete.
        send_digest(filter_new_strong_matches(jobs, previously_seen_ids=previously_seen_ids))

    return sorted(jobs, key=lambda j: j.match_score or 0, reverse=True)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the Naija Remote Job Hunter agent.")
    parser.add_argument("--min-strong-matches", type=int, default=5)
    parser.add_argument("--max-iterations", type=int, default=2)
    parser.add_argument("--max-candidates-to-score", type=int, default=DEFAULT_MAX_CANDIDATES_TO_SCORE)
    parser.add_argument("--no-notify", action="store_true", help="Skip the email digest for this run.")
    args = parser.parse_args()

    ranked = run(
        min_strong_matches=args.min_strong_matches,
        max_iterations=args.max_iterations,
        max_candidates_to_score=args.max_candidates_to_score,
        notify=not args.no_notify,
    )

    print(f"\n{len(ranked)} job(s) in shortlist:\n")
    for job in ranked:
        print(f"[{job.match_score:>3}] {job.title} @ {job.company} ({job.source}) - {job.url}")
        if job.match_reason:
            print(f"      {job.match_reason}")


if __name__ == "__main__":
    main()
