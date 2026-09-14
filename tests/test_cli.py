import io
import os

import httpx
import pytest
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

from job_hunter import cli, db
from job_hunter.nodes.generate_queries import QueryList
from job_hunter.nodes.score import MatchResult
from tests.conftest import FakeLLM

_EMPTY_WWR_RSS = '<?xml version="1.0"?><rss version="2.0"><channel><title>WWR</title></channel></rss>'


@pytest.fixture
def pg_url():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set - skipping tests that need a real Postgres instance.")
    conn = db.get_connection(url)
    conn.execute("TRUNCATE TABLE jobs")
    conn.execute("TRUNCATE TABLE profile")
    conn.commit()
    conn.close()
    return url


def _fake_cv_bytes() -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    doc.build([Paragraph("Experienced backend engineer.", styles["Normal"])])
    return buffer.getvalue()


def _remotive_raw(job_id: int, title: str) -> dict:
    return {
        "id": job_id,
        "url": f"https://remotive.com/remote-jobs/{job_id}",
        "title": title,
        "company_name": "Acme",
        "candidate_required_location": "Worldwide",
        "publication_date": "2026-08-01T00:00:00",
        "description": "desc",
    }


def _multi_source_client(remotive_jobs=()) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "weworkremotely" in host:
            return httpx.Response(200, text=_EMPTY_WWR_RSS)
        if "arbeitnow" in host:
            return httpx.Response(200, json={"data": []})
        if "remoteok" in host:
            return httpx.Response(200, json=[])
        if "remotive" in host:
            return httpx.Response(200, json={"jobs": list(remotive_jobs)})
        # jobicy and himalayas both key on "jobs", same as remotive.
        return httpx.Response(200, json={"jobs": []})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _seed_profile(url: str, *, role_titles=None) -> None:
    conn = db.get_connection(url)
    try:
        db.save_cv_bytes(conn, _fake_cv_bytes())
        preferences = {}
        if role_titles is not None:
            preferences["role_titles"] = role_titles
        db.save_preferences(conn, preferences)
    finally:
        conn.close()


def test_run_without_callback_uses_invoke_and_persists_to_db(pg_url):
    _seed_profile(pg_url)
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend"]),
            MatchResult: MatchResult(match_score=90, match_reason="Great fit"),
        }
    )
    http_client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])

    ranked = cli.run(
        database_url=pg_url,
        min_strong_matches=1,
        max_iterations=2,
        llm=llm,
        http_client=http_client,
        notify=False,
    )

    assert len(ranked) == 1
    assert ranked[0].match_score == 90

    conn = db.get_connection(pg_url)
    assert len(db.list_jobs(conn)) == 1


def test_run_raises_clear_error_without_cv(pg_url):
    # pg_url fixture truncates profile too, so no CV has been seeded here.
    with pytest.raises(RuntimeError, match="No CV on file"):
        cli.run(database_url=pg_url, llm=FakeLLM(QueryList(queries=[])))


def test_run_with_callback_reports_every_node_and_matches_invoke_result(pg_url):
    _seed_profile(pg_url)
    http_client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend"]),
            MatchResult: MatchResult(match_score=90, match_reason="Great fit"),
        }
    )

    seen_nodes = []
    ranked = cli.run(
        database_url=pg_url,
        min_strong_matches=1,
        max_iterations=2,
        llm=llm,
        http_client=http_client,
        notify=False,
        on_node_complete=seen_nodes.append,
    )

    assert seen_nodes == ["generate_queries", "retrieve", "validate_dedupe", "score"]
    assert len(ranked) == 1
    assert ranked[0].match_score == 90


def test_run_respects_notify_false(pg_url, monkeypatch):
    _seed_profile(pg_url)
    http_client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend"]),
            MatchResult: MatchResult(match_score=90, match_reason="Great fit"),
        }
    )

    calls = []
    monkeypatch.setattr(cli, "send_digest", lambda jobs: calls.append(jobs))

    cli.run(
        database_url=pg_url,
        min_strong_matches=1,
        llm=llm,
        http_client=http_client,
        notify=False,
    )

    assert calls == []


def test_run_calls_send_digest_when_notify_true(pg_url, monkeypatch):
    _seed_profile(pg_url)
    http_client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend"]),
            MatchResult: MatchResult(match_score=90, match_reason="Great fit"),
        }
    )

    calls = []
    monkeypatch.setattr(cli, "send_digest", lambda jobs: calls.append(jobs))

    cli.run(
        database_url=pg_url,
        min_strong_matches=1,
        llm=llm,
        http_client=http_client,
        notify=True,
    )

    assert len(calls) == 1
