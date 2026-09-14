from __future__ import annotations

from datetime import datetime, timezone

import httpx

from job_hunter.models import Job
from job_hunter.sources.geo import infer_nigeria_eligible_from_restrictions

HIMALAYAS_API_URL = "https://himalayas.app/jobs/api"


def _to_job(raw: dict) -> Job:
    restrictions = raw.get("locationRestrictions") or []
    pub_date = raw.get("pubDate")
    expiry_date = raw.get("expiryDate")
    now_ts = datetime.now(tz=timezone.utc).timestamp()
    return Job(
        job_id=f"himalayas:{raw['guid']}",
        title=raw.get("title", ""),
        company=raw.get("companyName", ""),
        location=", ".join(restrictions) if restrictions else None,
        remote_type="fully_remote",
        nigeria_eligible=infer_nigeria_eligible_from_restrictions(restrictions),
        salary_min=raw.get("minSalary"),
        salary_max=raw.get("maxSalary"),
        salary_currency=raw.get("currency"),
        posted_date=datetime.fromtimestamp(pub_date, tz=timezone.utc).date() if pub_date else None,
        source="himalayas",
        url=raw.get("applicationLink", ""),
        description=raw.get("description") or raw.get("excerpt", ""),
        still_open=(expiry_date > now_ts) if expiry_date else None,
    )


def fetch_jobs(*, limit: int | None = None, client: httpx.Client | None = None) -> list[Job]:
    """Fetch listings from Himalayas' free public API.

    `locationRestrictions` (empty = worldwide) drives Nigeria-eligibility
    inference, and `expiryDate` sets `still_open` directly - Himalayas is
    unusual among these sources in giving that signal explicitly rather than
    requiring a separate liveness check.
    """
    params = {}
    if limit:
        params["limit"] = limit

    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(HIMALAYAS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    return [_to_job(raw) for raw in data.get("jobs", [])]
