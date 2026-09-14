from datetime import date

import httpx

from job_hunter.sources import remoteok

_LEGAL_NOTICE = {"last_updated": 1788534826, "legal": "API Terms of Service notice"}


def _raw_job(**overrides) -> dict:
    raw = {
        "slug": "backend-engineer-acme-123",
        "id": "123",
        "epoch": 1788462746,
        "date": "2026-09-03T19:12:26+00:00",
        "company": "Acme",
        "position": "Backend Engineer",
        "tags": ["python"],
        "description": "Full description.",
        "location": "",
        "salary_min": 50000,
        "salary_max": 70000,
        "apply_url": "https://remoteOK.com/remote-jobs/backend-engineer-acme-123",
        "url": "https://remoteOK.com/remote-jobs/backend-engineer-acme-123",
    }
    raw.update(overrides)
    return raw


def _client_returning(jobs: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[_LEGAL_NOTICE, *jobs])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_jobs_skips_legal_notice_entry():
    client = _client_returning([_raw_job()])
    jobs = remoteok.fetch_jobs(client=client)
    assert len(jobs) == 1


def test_fetch_jobs_maps_fields_correctly():
    client = _client_returning([_raw_job()])
    job = remoteok.fetch_jobs(client=client)[0]

    assert job.job_id == "remoteok:123"
    assert job.title == "Backend Engineer"
    assert job.company == "Acme"
    assert job.source == "remoteok"
    assert job.remote_type == "fully_remote"
    assert job.salary_min == 50000
    assert job.salary_max == 70000
    assert job.salary_currency == "USD"
    assert job.posted_date == date(2026, 9, 3)


def test_empty_location_is_unclear():
    client = _client_returning([_raw_job(location="")])
    jobs = remoteok.fetch_jobs(client=client)
    assert jobs[0].nigeria_eligible is None


def test_worldwide_location_marks_eligible():
    client = _client_returning([_raw_job(location="Worldwide")])
    jobs = remoteok.fetch_jobs(client=client)
    assert jobs[0].nigeria_eligible is True


def test_no_salary_means_no_currency():
    client = _client_returning([_raw_job(salary_min=None, salary_max=None)])
    jobs = remoteok.fetch_jobs(client=client)
    assert jobs[0].salary_currency is None


def test_fetch_jobs_handles_only_legal_notice():
    client = _client_returning([])
    assert remoteok.fetch_jobs(client=client) == []
