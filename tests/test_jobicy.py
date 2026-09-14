from datetime import date

import httpx

from job_hunter.sources import jobicy


def _raw_job(**overrides) -> dict:
    raw = {
        "id": 152566,
        "url": "https://jobicy.com/jobs/152566-support-engineer",
        "jobTitle": "Support Engineer",
        "companyName": "Roboflow",
        "jobGeo": "USA",
        "jobLevel": "Any",
        "jobExcerpt": "Short excerpt.",
        "jobDescription": "<h3>Full description.</h3>",
        "pubDate": "2026-09-05T06:08:42+00:00",
    }
    raw.update(overrides)
    return raw


def _client_returning(jobs: list[dict]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jobs": jobs})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_jobs_maps_fields_correctly():
    client = _client_returning([_raw_job()])
    jobs = jobicy.fetch_jobs(client=client)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_id == "jobicy:152566"
    assert job.title == "Support Engineer"
    assert job.company == "Roboflow"
    assert job.source == "jobicy"
    assert job.remote_type == "fully_remote"
    assert job.nigeria_eligible is False
    assert job.posted_date == date(2026, 9, 5)
    assert job.description == "<h3>Full description.</h3>"


def test_worldwide_geo_marks_eligible():
    client = _client_returning([_raw_job(jobGeo="Worldwide")])
    jobs = jobicy.fetch_jobs(client=client)
    assert jobs[0].nigeria_eligible is True


def test_falls_back_to_excerpt_when_description_missing():
    raw = _raw_job()
    del raw["jobDescription"]
    client = _client_returning([raw])
    jobs = jobicy.fetch_jobs(client=client)
    assert jobs[0].description == "Short excerpt."


def test_fetch_jobs_handles_empty_results():
    client = _client_returning([])
    assert jobicy.fetch_jobs(client=client) == []
