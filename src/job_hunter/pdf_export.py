from __future__ import annotations

import io
from datetime import date, datetime
from html import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from job_hunter.models import Job

_styles = getSampleStyleSheet()
_title_style = _styles["Title"]
_meta_style = ParagraphStyle("meta", parent=_styles["Normal"], textColor=colors.grey, spaceAfter=12)
_job_title_style = ParagraphStyle("job_title", parent=_styles["Heading3"], spaceAfter=2)
_job_meta_style = ParagraphStyle("job_meta", parent=_styles["Normal"], textColor=colors.grey, spaceAfter=6)
_reason_style = ParagraphStyle("reason", parent=_styles["Normal"], spaceAfter=14)


def _job_meta_line(job: Job) -> str:
    parts = [job.source, job.remote_type]
    if job.nigeria_eligible is True:
        parts.append("Nigeria-eligible")
    elif job.nigeria_eligible is False:
        parts.append("Nigeria-restricted")
    if job.salary_min or job.salary_max:
        parts.append(f"{job.salary_min or '?'}-{job.salary_max or '?'} {job.salary_currency or ''}".strip())
    if job.posted_date:
        parts.append(f"posted {job.posted_date.isoformat()}")
    return " · ".join(escape(str(p)) for p in parts)


def export_jobs_to_pdf(jobs: list[Job], *, generated_at: date | None = None) -> bytes:
    """Render a ranked job shortlist as a PDF, returned as bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    generated_at = generated_at or datetime.now().date()
    elements = [
        Paragraph("Nigerian Remote Job Hunter — Shortlist", _title_style),
        Paragraph(f"Generated {generated_at.isoformat()} · {len(jobs)} job(s)", _meta_style),
    ]

    for job in jobs:
        score = job.match_score if job.match_score is not None else "—"
        elements.append(Paragraph(f"[{score}] {escape(job.title)} — {escape(job.company)}", _job_title_style))
        elements.append(Paragraph(_job_meta_line(job), _job_meta_style))
        if job.match_reason:
            elements.append(Paragraph(escape(job.match_reason), _reason_style))
        elements.append(Paragraph(f'<link href="{escape(job.url)}">{escape(job.url)}</link>', _job_meta_style))
        elements.append(Spacer(1, 12))

    doc.build(elements)
    return buffer.getvalue()
