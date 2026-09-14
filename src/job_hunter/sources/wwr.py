from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from job_hunter.models import Job
from job_hunter.sources.geo import infer_nigeria_eligible_from_text

WWR_RSS_URL = "https://weworkremotely.com/remote-jobs.rss"


def _split_company_and_title(raw_title: str) -> tuple[str, str]:
    if ": " in raw_title:
        company, _, title = raw_title.partition(": ")
        return company, title
    return "", raw_title


def _parse_pub_date(pub_date: str | None):
    if not pub_date:
        return None
    try:
        return parsedate_to_datetime(pub_date).date()
    except (TypeError, ValueError):
        return None


def _item_text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _to_job(item: ET.Element) -> Job:
    company, title = _split_company_and_title(_item_text(item, "title"))
    region = _item_text(item, "region")
    url = _item_text(item, "link") or _item_text(item, "guid")

    return Job(
        job_id=f"wwr:{url}",
        title=title,
        company=company,
        location=region or None,
        remote_type="fully_remote",
        nigeria_eligible=infer_nigeria_eligible_from_text(region, default_when_specific=False),
        posted_date=_parse_pub_date(_item_text(item, "pubDate")),
        source="wwr",
        url=url,
        description=_item_text(item, "description"),
    )


def fetch_jobs(*, client: httpx.Client | None = None) -> list[Job]:
    """Fetch listings from We Work Remotely's official public RSS feed.

    WWR's ToS bans scraping the site directly but allows use of this RSS/API
    feed for commercial/personal use, per project-about.md §3. Title comes as
    "Company: Job Title" in this feed and is split accordingly.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get(WWR_RSS_URL)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    finally:
        if owns_client:
            client.close()

    return [_to_job(item) for item in root.findall(".//item")]
