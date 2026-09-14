from datetime import date

import httpx
import pytest

from job_hunter.sources import remotive


def _sample_raw_job(**overrides) -> dict:
    raw = {
        "id": 2086540,
        "url": "https://remotive.com/remote-jobs/sales/inside-sales-contractor-2086540",
        "title": "Inside Sales Contractor",
        "company_name": "Credit Wellness, LLC",
        "candidate_required_location": "Worldwide",
        "publication_date": "2026-08-08T21:48:06",
        "description": "<p>About us...</p>",
    }
    raw.update(overrides)
    return raw


def _client_returning(payload: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("Worldwide", True),
        ("Anywhere", True),
        ("Nigeria", True),
        ("Africa (Remote)", True),
        ("USA Only", False),
        ("UK Only", False),
        ("United States", False),
        ("Germany", False),
        ("USA, Canada", False),
        ("", None),
    ],
)
def test_infer_nigeria_eligible(location, expected):
    assert remotive._infer_nigeria_eligible(location) is expected


def test_fetch_jobs_maps_fields_correctly():
    client = _client_returning({"jobs": [_sample_raw_job()]})
    jobs = remotive.fetch_jobs(client=client)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_id == "remotive:2086540"
    assert job.title == "Inside Sales Contractor"
    assert job.company == "Credit Wellness, LLC"
    assert job.source == "remotive"
    assert job.remote_type == "fully_remote"
    assert job.nigeria_eligible is True
    assert job.posted_date == date(2026, 8, 8)
    assert job.url == _sample_raw_job()["url"]


def test_fetch_jobs_handles_empty_results():
    client = _client_returning({"jobs": []})
    assert remotive.fetch_jobs(client=client) == []


def test_fetch_jobs_handles_missing_publication_date():
    raw = _sample_raw_job()
    del raw["publication_date"]
    client = _client_returning({"jobs": [raw]})
    jobs = remotive.fetch_jobs(client=client)
    assert jobs[0].posted_date is None


def test_fetch_jobs_passes_query_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"jobs": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    remotive.fetch_jobs(search="python", category="software-dev", limit=10, client=client)

    assert captured["params"] == {"search": "python", "category": "software-dev", "limit": "10"}


def test_fetch_jobs_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        remotive.fetch_jobs(client=client)
