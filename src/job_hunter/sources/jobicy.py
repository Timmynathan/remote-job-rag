from __future__ import annotations

from datetime import datetime

import httpx

from job_hunter.models import Job
from job_hunter.sources.geo import infer_nigeria_eligible_from_text

JOBICY_API_URL = "https://jobicy.com/api/v2/remote-jobs"


def _parse_pub_date(pub_date: str | None):
    if not pub_date:
        return None
    try:
        return datetime.fromisoformat(pub_date).date()
    except ValueError:
        return None


def _to_job(raw: dict) -> Job:
    geo = raw.get("jobGeo", "")
    return Job(
        job_id=f"jobicy:{raw['id']}",
        title=raw.get("jobTitle", ""),
        company=raw.get("companyName", ""),
        location=geo or None,
        remote_type="fully_remote",
        nigeria_eligible=infer_nigeria_eligible_from_text(geo, default_when_specific=False),
        posted_date=_parse_pub_date(raw.get("pubDate")),
        source="jobicy",
        url=raw.get("url", ""),
        description=raw.get("jobDescription") or raw.get("jobExcerpt", ""),
    )


def fetch_jobs(*, count: int | None = None, client: httpx.Client | None = None) -> list[Job]:
    """Fetch listings from Jobicy's free public API.

    Jobicy's terms require crediting Jobicy with a direct link back, and all
    application buttons must redirect to their original job URL (satisfied by
    using their `url` field as-is).
    """
    params = {}
    if count:
        params["count"] = count

    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(JOBICY_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    return [_to_job(raw) for raw in data.get("jobs", [])]
