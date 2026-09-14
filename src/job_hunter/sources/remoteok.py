from __future__ import annotations

from datetime import datetime

import httpx

from job_hunter.models import Job
from job_hunter.sources.geo import infer_nigeria_eligible_from_text

REMOTEOK_API_URL = "https://remoteok.com/api"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NaijaJobHunter/1.0)"}


def _parse_date(date_str: str | None):
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).date()
    except ValueError:
        return None


def _to_job(raw: dict) -> Job:
    location = raw.get("location", "")
    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")
    return Job(
        job_id=f"remoteok:{raw['id']}",
        title=raw.get("position", ""),
        company=raw.get("company", ""),
        location=location or None,
        remote_type="fully_remote",
        nigeria_eligible=infer_nigeria_eligible_from_text(location, default_when_specific=False),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="USD" if (salary_min or salary_max) else None,
        posted_date=_parse_date(raw.get("date")),
        source="remoteok",
        url=raw.get("url") or raw.get("apply_url", ""),
        description=raw.get("description", ""),
    )


def fetch_jobs(*, client: httpx.Client | None = None) -> list[Job]:
    """Fetch listings from RemoteOK's free public API.

    RemoteOK's terms require linking back to the RemoteOK job URL (satisfied
    by using their `url` field as-is); their free feed is 24h-delayed.
    RemoteOK stalls/blocks requests without a real browser-like User-Agent,
    hence the default header here.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=30, headers=_HEADERS)
    try:
        response = client.get(REMOTEOK_API_URL)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    # The first array element is always a legal/ToS notice object, not a job.
    return [_to_job(raw) for raw in data if "id" in raw]
