from __future__ import annotations

from datetime import datetime

import httpx

from job_hunter.models import Job
from job_hunter.sources.geo import infer_nigeria_eligible_from_text

REMOTIVE_API_URL = "https://remotive.com/api/remote-jobs"


def _infer_nigeria_eligible(candidate_required_location: str) -> bool | None:
    return infer_nigeria_eligible_from_text(candidate_required_location, default_when_specific=False)


def _parse_posted_date(publication_date: str | None):
    if not publication_date:
        return None
    try:
        return datetime.fromisoformat(publication_date).date()
    except ValueError:
        return None


def _to_job(raw: dict) -> Job:
    location = raw.get("candidate_required_location", "")
    return Job(
        job_id=f"remotive:{raw['id']}",
        title=raw.get("title", ""),
        company=raw.get("company_name", ""),
        location=location or None,
        remote_type="fully_remote",
        nigeria_eligible=_infer_nigeria_eligible(location),
        posted_date=_parse_posted_date(raw.get("publication_date")),
        source="remotive",
        url=raw.get("url", ""),
        description=raw.get("description", ""),
    )


def fetch_jobs(
    *,
    search: str | None = None,
    category: str | None = None,
    limit: int | None = None,
    client: httpx.Client | None = None,
) -> list[Job]:
    """Fetch listings from Remotive's free public API.

    Remotive's terms require linking back to their job URL (satisfied by
    using their `url` field as-is) and cap polling at a few requests/day, so
    this should only be called from the scheduled/manual run, not in a loop.
    """
    params = {}
    if search:
        params["search"] = search
    if category:
        params["category"] = category
    if limit:
        params["limit"] = limit

    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(REMOTIVE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    return [_to_job(raw) for raw in data.get("jobs", [])]
