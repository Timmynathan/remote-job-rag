from __future__ import annotations

import os
from collections.abc import Callable
from html import escape

import resend

from job_hunter.models import Job
from job_hunter.nodes.refine import STRONG_MATCH_THRESHOLD

DEFAULT_FROM_EMAIL = "onboarding@resend.dev"


def _render_html(jobs: list[Job]) -> str:
    items = "".join(
        f"<li><strong>[{job.match_score}] {escape(job.title)}</strong> @ {escape(job.company)} "
        f"({escape(job.source)})<br>{escape(job.match_reason or '')}"
        f'<br><a href="{escape(job.url)}">View posting</a></li>'
        for job in jobs
    )
    return f"<ul>{items}</ul>"


def send_digest(
    jobs: list[Job],
    *,
    to_email: str | None = None,
    from_email: str | None = None,
    api_key: str | None = None,
    send_fn: Callable[[dict], object] | None = None,
) -> None:
    """Email a digest of newly-found strong matches via Resend.

    A no-op if there's nothing to report, or if RESEND_API_KEY/DIGEST_TO_EMAIL
    aren't configured yet - a run should never fail just because
    notification isn't set up.
    """
    if not jobs:
        return

    api_key = api_key or os.environ.get("RESEND_API_KEY")
    to_email = to_email or os.environ.get("DIGEST_TO_EMAIL")
    from_email = from_email or os.environ.get("DIGEST_FROM_EMAIL", DEFAULT_FROM_EMAIL)

    if not api_key or not to_email:
        return

    if send_fn is None:
        resend.api_key = api_key
        send_fn = resend.Emails.send

    count = len(jobs)
    send_fn(
        {
            "from": from_email,
            "to": [to_email],
            "subject": f"{count} new strong match{'es' if count != 1 else ''} found",
            "html": _render_html(jobs),
        }
    )


def filter_new_strong_matches(jobs: list[Job], *, previously_seen_ids: set[str]) -> list[Job]:
    """Only jobs that weren't already in the database before this run, and
    that clear the strong-match threshold - avoids re-notifying about the
    same posting every day it stays unreviewed.
    """
    return [
        job
        for job in jobs
        if job.job_id not in previously_seen_ids and (job.match_score or 0) >= STRONG_MATCH_THRESHOLD
    ]
