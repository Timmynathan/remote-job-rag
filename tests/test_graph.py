import httpx

from job_hunter.graph import build_graph
from job_hunter.nodes.generate_queries import QueryList
from job_hunter.nodes.score import MatchResult
from tests.conftest import FakeLLM


_EMPTY_WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>WWR</title></channel></rss>"""


def _client_returning(remotive_jobs: list[dict]) -> httpx.Client:
    """Only Remotive returns data; every other source gets an empty response
    of its own expected shape, so the graph-level assertions stay accurate
    now that retrieve_node calls all six sources."""

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host or ""
        if "remotive" in host:
            return httpx.Response(200, json={"jobs": remotive_jobs})
        if "arbeitnow" in host:
            return httpx.Response(200, json={"data": []})
        if "remoteok" in host:
            return httpx.Response(200, json=[])
        if "weworkremotely" in host:
            return httpx.Response(200, text=_EMPTY_WWR_RSS)
        # jobicy and himalayas both key on "jobs", same as remotive.
        return httpx.Response(200, json={"jobs": []})

    return httpx.Client(transport=httpx.MockTransport(handler))


def _raw_job(job_id: int, title: str) -> dict:
    return {
        "id": job_id,
        "url": f"https://remotive.com/remote-jobs/{job_id}",
        "title": title,
        "company_name": "Acme",
        "candidate_required_location": "Worldwide",
        "publication_date": "2026-08-01T00:00:00",
        "description": "desc",
    }


def test_graph_finishes_after_one_pass_when_matches_are_strong():
    app = build_graph()
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend engineer"]),
            MatchResult: MatchResult(match_score=90, match_reason="Great fit"),
        }
    )
    http_client = _client_returning([_raw_job(1, "Backend Engineer")])

    final_state = app.invoke(
        {
            "cv_text": "Experienced backend engineer",
            "preferences": {"role_titles": ["Backend Engineer"]},
            "min_strong_matches": 1,
            "max_iterations": 2,
            "llm": llm,
            "http_client": http_client,
        }
    )

    assert final_state["iteration"] == 1
    assert len(final_state["candidates"]) == 1
    job = final_state["candidates"][0]
    assert job.still_open is True
    assert job.match_score is not None


def test_graph_stops_at_max_iterations_without_enough_strong_matches():
    app = build_graph()
    llm = FakeLLM(
        {
            QueryList: QueryList(queries=["backend engineer"]),
            MatchResult: MatchResult(match_score=10, match_reason="Weak fit"),
        }
    )
    http_client = _client_returning([_raw_job(1, "Backend Engineer")])

    final_state = app.invoke(
        {
            "cv_text": "Experienced backend engineer",
            "preferences": {},
            "min_strong_matches": 5,
            "max_iterations": 2,
            "llm": llm,
            "http_client": http_client,
        }
    )

    assert final_state["iteration"] == 2
