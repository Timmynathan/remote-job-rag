import httpx

from job_hunter.models import Job
from job_hunter.nodes.retrieve import retrieve_node

_EMPTY_WWR_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>WWR</title></channel></rss>"""


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


def _multi_source_client(
    *,
    remotive_jobs=(),
    arbeitnow_jobs=(),
    jobicy_jobs=(),
    remoteok_jobs=(),
    himalayas_jobs=(),
    wwr_xml=None,
    fail_hosts=(),
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if host in fail_hosts:
            return httpx.Response(500)
        if "remotive" in host:
            return httpx.Response(200, json={"jobs": list(remotive_jobs)})
        if "arbeitnow" in host:
            return httpx.Response(200, json={"data": list(arbeitnow_jobs)})
        if "jobicy" in host:
            return httpx.Response(200, json={"jobs": list(jobicy_jobs)})
        if "remoteok" in host:
            return httpx.Response(200, json=[{"legal": "notice"}, *remoteok_jobs])
        if "himalayas" in host:
            return httpx.Response(200, json={"jobs": list(himalayas_jobs)})
        if "weworkremotely" in host:
            return httpx.Response(200, text=wwr_xml or _EMPTY_WWR_RSS)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_retrieve_node_fetches_from_remotive():
    client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])
    state = {"queries": ["backend"], "http_client": client}
    result = retrieve_node(state)
    titles = [j.title for j in result["candidates"]]
    assert titles == ["Backend Engineer"]


def test_retrieve_node_merges_jobs_from_multiple_sources():
    client = _multi_source_client(
        remotive_jobs=[_remotive_raw(1, "Backend Engineer")],
        arbeitnow_jobs=[
            {
                "slug": "frontend-dev-1",
                "company_name": "Beta",
                "title": "Frontend Developer",
                "description": "desc",
                "remote": True,
                "url": "https://www.arbeitnow.com/jobs/frontend-dev-1",
                "location": "Worldwide",
                "created_at": 1788608414,
            }
        ],
    )
    state = {"queries": [], "http_client": client}
    result = retrieve_node(state)
    sources = {j.source for j in result["candidates"]}
    assert sources == {"remotive", "arbeitnow"}


def test_retrieve_node_preserves_existing_enriched_candidates():
    existing = Job(
        job_id="remotive:1",
        title="Backend Engineer",
        company="Acme",
        source="remotive",
        url="https://remotive.com/remote-jobs/1",
        match_score=85,
        match_reason="Strong fit",
    )
    client = _multi_source_client(remotive_jobs=[_remotive_raw(1, "Backend Engineer")])
    state = {"queries": ["backend"], "candidates": [existing], "http_client": client}

    result = retrieve_node(state)

    assert len(result["candidates"]) == 1
    assert result["candidates"][0].match_score == 85


def test_retrieve_node_accumulates_new_candidates_across_passes():
    client = _multi_source_client(remotive_jobs=[_remotive_raw(2, "New Role")])
    existing = Job(
        job_id="remotive:1",
        title="Backend Engineer",
        company="Acme",
        source="remotive",
        url="https://remotive.com/remote-jobs/1",
    )
    state = {"queries": ["python"], "candidates": [existing], "http_client": client}

    result = retrieve_node(state)

    job_ids = {j.job_id for j in result["candidates"]}
    assert job_ids == {"remotive:1", "remotive:2"}


def test_retrieve_node_makes_only_one_http_call_per_source():
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        if request.url.host and "remotive" in request.url.host:
            call_count += 1
        if request.url.host and "weworkremotely" in request.url.host:
            return httpx.Response(200, text=_EMPTY_WWR_RSS)
        if request.url.host and "arbeitnow" in request.url.host:
            return httpx.Response(200, json={"data": []})
        if request.url.host and "remoteok" in request.url.host:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"jobs": [_remotive_raw(1, "Backend Engineer")]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    state = {"queries": ["backend", "frontend", "ai engineer"], "http_client": client}

    retrieve_node(state)

    assert call_count == 1


def test_retrieve_node_skips_a_failing_source_without_crashing():
    client = _multi_source_client(
        remotive_jobs=[_remotive_raw(1, "Backend Engineer")],
        fail_hosts=("www.arbeitnow.com",),
    )
    state = {"queries": [], "http_client": client}

    result = retrieve_node(state)

    assert [j.title for j in result["candidates"]] == ["Backend Engineer"]
