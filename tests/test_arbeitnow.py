import httpx

from job_hunter.sources import arbeitnow


def _raw_job(**overrides) -> dict:
    raw = {
        "slug": "backend-engineer-berlin-123",
        "company_name": "Acme GmbH",
        "title": "Backend Engineer",
        "description": "<p>Build things.</p>",
        "remote": True,
        "url": "https://www.arbeitnow.com/jobs/companies/acme/backend-engineer-berlin-123",
        "tags": ["Python"],
        "job_types": ["Full Time"],
        "location": "Germany",
        "created_at": 1788608414,
    }
    raw.update(overrides)
    return raw


def _client_returning(jobs: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": jobs})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_jobs_maps_fields_correctly():
    client = _client_returning([_raw_job()])
    jobs = arbeitnow.fetch_jobs(client=client)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_id == "arbeitnow:backend-engineer-berlin-123"
    assert job.title == "Backend Engineer"
    assert job.company == "Acme GmbH"
    assert job.source == "arbeitnow"
    assert job.remote_type == "fully_remote"
    # Arbeitnow's location is a base location, not an eligibility signal.
    assert job.nigeria_eligible is None


def test_fetch_jobs_filters_out_non_remote_jobs():
    client = _client_returning([_raw_job(remote=False)])
    assert arbeitnow.fetch_jobs(client=client) == []


def test_worldwide_location_marks_eligible():
    client = _client_returning([_raw_job(location="Worldwide")])
    jobs = arbeitnow.fetch_jobs(client=client)
    assert jobs[0].nigeria_eligible is True


def test_fetch_jobs_handles_empty_results():
    client = _client_returning([])
    assert arbeitnow.fetch_jobs(client=client) == []
