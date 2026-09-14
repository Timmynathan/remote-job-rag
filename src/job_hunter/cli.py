from __future__ import annotations

import argparse
import os
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv

from job_hunter import db
from job_hunter.cv_parser import extract_text_from_bytes
from job_hunter.graph import build_graph
from job_hunter.nodes.score import DEFAULT_MAX_CANDIDATES_TO_SCORE
from job_hunter.notify import filter_new_strong_matches, send_digest


def _resolve_database_url(database_url: str | None) -> str:
    database_url = database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env (or your hosting platform's secrets) - "
            "see README.md for how to get one from Neon."
        )
    return database_url


def run(
    *,
    database_url: str | None = None,
    min_strong_matches: int = 5,
    max_iterations: int = 2,
    max_candidates_to_score: int = DEFAULT_MAX_CANDIDATES_TO_SCORE,
    notify: bool = True,
    on_node_complete: Callable[[str], None] | None = None,
    llm: Any = None,
    http_client: Any = None,
) -> list:
    url = _resolve_database_url(database_url)

    # Two separate short-lived connections rather than one held open for the
    # whole run: the graph execution in between can take minutes (external
    # API + LLM calls), and a serverless Postgres like Neon can suspend/drop
    # idle connections in that window.
    conn = db.get_connection(url)
    try:
        cv_bytes = db.get_cv_bytes(conn)
        if cv_bytes is None:
            raise RuntimeError("No CV on file yet - upload one via the dashboard's CV & Preferences form first.")
        cv_text = extract_text_from_bytes(cv_bytes)
        preferences = db.get_preferences(conn)
    finally:
        conn.close()

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

    conn = db.get_connection(url)
    try:
        previously_seen_ids = {j.job_id for j in db.list_jobs(conn)}
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
    parser = argparse.ArgumentParser(description="Run the My Job Hunter agent.")
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
