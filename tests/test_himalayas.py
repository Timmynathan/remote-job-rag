from datetime import datetime, timedelta, timezone

import httpx

from job_hunter.sources import himalayas


def _raw_job(**overrides) -> dict:
    raw = {
        "title": "Backend Engineer",
        "excerpt": "Short excerpt.",
        "companyName": "Fresh Consulting",
        "minSalary": 75000,
        "maxSalary": 95000,
        "currency": "USD",
        "locationRestrictions": ["United States"],
        "description": "<p>Full description.</p>",
        "pubDate": int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp()),
        "expiryDate": int((datetime.now(tz=timezone.utc) + timedelta(days=30)).timestamp()),
        "applicationLink": "https://himalayas.app/companies/fresh-consulting/jobs/backend-engineer",
        "guid": "https://himalayas.app/companies/fresh-consulting/jobs/backend-engineer",
    }
    raw.update(overrides)
    return raw


def _client_returning(jobs: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": jobs})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_jobs_maps_fields_correctly():
    client = _client_returning([_raw_job()])
    jobs = himalayas.fetch_jobs(client=client)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_id == "himalayas:https://himalayas.app/companies/fresh-consulting/jobs/backend-engineer"
    assert job.title == "Backend Engineer"
    assert job.company == "Fresh Consulting"
    assert job.source == "himalayas"
    assert job.salary_min == 75000
    assert job.salary_max == 95000
    assert job.salary_currency == "USD"
    assert job.nigeria_eligible is False
    assert job.still_open is True


def test_empty_location_restrictions_means_worldwide():
    client = _client_returning([_raw_job(locationRestrictions=[])])
    jobs = himalayas.fetch_jobs(client=client)
    assert jobs[0].nigeria_eligible is True


def test_expired_job_marked_not_still_open():
    past_expiry = int((datetime.now(tz=timezone.utc) - timedelta(days=1)).timestamp())
    client = _client_returning([_raw_job(expiryDate=past_expiry)])
    jobs = himalayas.fetch_jobs(client=client)
    assert jobs[0].still_open is False


def test_falls_back_to_excerpt_when_description_missing():
    raw = _raw_job()
    del raw["description"]
    client = _client_returning([raw])
    jobs = himalayas.fetch_jobs(client=client)
    assert jobs[0].description == "Short excerpt."


def test_fetch_jobs_handles_empty_results():
    client = _client_returning([])
    assert himalayas.fetch_jobs(client=client) == []
