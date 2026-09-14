import pytest
from pydantic import ValidationError

from job_hunter.models import Job


def _minimal_job(**overrides):
    fields = {
        "job_id": "remotive:123",
        "title": "Backend Engineer",
        "company": "Acme",
        "source": "remotive",
        "url": "https://example.com/jobs/123",
    }
    fields.update(overrides)
    return Job(**fields)


def test_minimal_job_has_expected_defaults():
    job = _minimal_job()
    assert job.remote_type == "unclear"
    assert job.status == "new"
    assert job.match_score is None
    assert job.description == ""


def test_match_score_within_bounds_is_accepted():
    job = _minimal_job(match_score=87)
    assert job.match_score == 87


@pytest.mark.parametrize("score", [-1, 101])
def test_match_score_out_of_bounds_is_rejected(score):
    with pytest.raises(ValidationError):
        _minimal_job(match_score=score)


def test_invalid_remote_type_is_rejected():
    with pytest.raises(ValidationError):
        _minimal_job(remote_type="fully_onsite")


def test_invalid_status_is_rejected():
    with pytest.raises(ValidationError):
        _minimal_job(status="archived")


def test_missing_required_field_is_rejected():
    with pytest.raises(ValidationError):
        Job(title="Backend Engineer", company="Acme", source="remotive", url="https://example.com")
