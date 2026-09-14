from __future__ import annotations

from datetime import datetime, timezone

import httpx

from job_hunter.models import Job
from job_hunter.sources.geo import infer_nigeria_eligible_from_text

ARBEITNOW_API_URL = "https://www.arbeitnow.com/api/job-board-api"


def _to_job(raw: dict) -> Job:
    location = raw.get("location", "")
    created_at = raw.get("created_at")
    return Job(
        job_id=f"arbeitnow:{raw['slug']}",
        title=raw.get("title", ""),
        company=raw.get("company_name", ""),
        location=location or None,
        remote_type="fully_remote",
        # Arbeitnow's `location` is the job's base location, not a stated
        # candidate-eligibility restriction, so a named place is genuinely
        # unclear rather than a confirmed non-fit (unlike Remotive/Jobicy).
        nigeria_eligible=infer_nigeria_eligible_from_text(location, default_when_specific=None),
        posted_date=datetime.fromtimestamp(created_at, tz=timezone.utc).date() if created_at else None,
        source="arbeitnow",
        url=raw.get("url", ""),
        description=raw.get("description", ""),
    )


def fetch_jobs(*, client: httpx.Client | None = None) -> list[Job]:
    """Fetch listings from Arbeitnow's free public API.

    Arbeitnow's terms require linking back to arbeitnow.com (satisfied by
    using their `url` field as-is). Only jobs flagged `remote=True` are kept,
    since Arbeitnow also lists on-site/hybrid roles.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(ARBEITNOW_API_URL)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    return [_to_job(raw) for raw in data.get("data", []) if raw.get("remote")]
