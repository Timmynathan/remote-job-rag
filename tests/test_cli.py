import httpx
import yaml
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate

from job_hunter import cli, db
from job_hunter.nodes.generate_queries import QueryList
from job_hunter.nodes.score import MatchResult
from tests.conftest import FakeLLM

_EMPTY_WWR_RSS = '<?xml version="1.0"?><rss version="2.0"><channel><title>WWR</title></channel></rss>'


def _make_cv_pdf(path):
    doc = SimpleDocTemplate(str(path))
    styles = getSampleStyleSheet()
    doc.build([Paragraph("Experienced backend engineer.", styles["Normal"])])


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


def _setup(tmp_path, *, role_titles=None):
    cv_path = tmp_path / "CV.pdf"
    _make_cv_pdf(cv_path)

    preferences_path = tmp_path / "preferences.yaml"
    preferences = {"min_strong_matches": 1}
    if role_titles is not None:
        preferences["role_titles"] = role_titles
    preferences_path.write_text(yaml.safe_dump(preferences))

    db_path = tmp_path / "jobs.db"
    return cv_path, preferences_path, db_path


def test_run_without_callback_uses_invoke_and_persists_to_db(tmp_path):
    cv_path, preferences_path, db_path = _setup(tmp_path)
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend"]),
            MatchResult: MatchResult(match_score=90, match_reason="Great fit"),
        }
    )
    http_client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])

    ranked = cli.run(
        cv_path=cv_path,
        preferences_path=preferences_path,
        db_path=db_path,
        min_strong_matches=1,
        max_iterations=2,
        llm=llm,
        http_client=http_client,
        notify=False,
    )

    assert len(ranked) == 1
    assert ranked[0].match_score == 90

    conn = db.get_connection(db_path)
    assert len(db.list_jobs(conn)) == 1


def test_run_with_callback_reports_every_node_and_matches_invoke_result(tmp_path):
    cv_path, preferences_path, db_path = _setup(tmp_path)
    http_client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend"]),
            MatchResult: MatchResult(match_score=90, match_reason="Great fit"),
        }
    )

    seen_nodes = []
    ranked = cli.run(
        cv_path=cv_path,
        preferences_path=preferences_path,
        db_path=db_path,
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


def test_run_respects_notify_false(tmp_path, monkeypatch):
    cv_path, preferences_path, db_path = _setup(tmp_path)
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
        cv_path=cv_path,
        preferences_path=preferences_path,
        db_path=db_path,
        min_strong_matches=1,
        llm=llm,
        http_client=http_client,
        notify=False,
    )

    assert calls == []


def test_run_calls_send_digest_when_notify_true(tmp_path, monkeypatch):
    cv_path, preferences_path, db_path = _setup(tmp_path)
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
        cv_path=cv_path,
        preferences_path=preferences_path,
        db_path=db_path,
        min_strong_matches=1,
        llm=llm,
        http_client=http_client,
        notify=True,
    )

    assert len(calls) == 1
