from datetime import date

from job_hunter.models import Job
from job_hunter.pdf_export import export_jobs_to_pdf


def _job(**overrides) -> Job:
    fields = {
        "job_id": "remotive:1",
        "title": "Backend Engineer",
        "company": "Acme",
        "source": "remotive",
        "url": "https://example.com",
        "match_score": 85,
        "match_reason": "Strong fit",
        "posted_date": date(2026, 9, 1),
        "salary_min": 60000,
        "salary_max": 90000,
        "salary_currency": "USD",
        "nigeria_eligible": True,
    }
    fields.update(overrides)
    return Job(**fields)


def test_export_produces_valid_pdf_bytes():
    pdf_bytes = export_jobs_to_pdf([_job()])
    assert pdf_bytes[:4] == b"%PDF"
    assert len(pdf_bytes) > 0


def test_export_handles_empty_job_list():
    pdf_bytes = export_jobs_to_pdf([])
    assert pdf_bytes[:4] == b"%PDF"


def test_export_handles_jobs_with_missing_optional_fields():
    bare_job = Job(
        job_id="remotive:2",
        title="Frontend Engineer",
        company="Beta",
        source="remotive",
        url="https://example.com/2",
    )
    pdf_bytes = export_jobs_to_pdf([bare_job])
    assert pdf_bytes[:4] == b"%PDF"


def test_export_handles_html_special_characters_in_fields():
    malicious = _job(title="<b>Injected</b> & \"quoted\"", match_reason="A <script> tag & an ampersand")
    pdf_bytes = export_jobs_to_pdf([malicious])
    assert pdf_bytes[:4] == b"%PDF"


def test_export_accepts_explicit_generated_at():
    pdf_bytes = export_jobs_to_pdf([_job()], generated_at=date(2026, 1, 1))
    assert pdf_bytes[:4] == b"%PDF"
