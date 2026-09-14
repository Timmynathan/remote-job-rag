import pytest

from job_hunter import db
from job_hunter.models import Job


@pytest.fixture
def conn():
    connection = db.get_connection(":memory:")
    yield connection
    connection.close()


def _job(**overrides) -> Job:
    fields = {
        "job_id": "remotive:123",
        "title": "Backend Engineer",
        "company": "Acme",
        "source": "remotive",
        "url": "https://example.com/jobs/123",
    }
    fields.update(overrides)
    return Job(**fields)


def test_upsert_then_get_roundtrips(conn):
    db.upsert_job(conn, _job())
    fetched = db.get_job(conn, "remotive:123")
    assert fetched.title == "Backend Engineer"
    assert fetched.status == "new"


def test_get_missing_job_returns_none(conn):
    assert db.get_job(conn, "does-not-exist") is None


def test_upsert_preserves_existing_status_across_runs(conn):
    db.upsert_job(conn, _job())
    db.update_status(conn, "remotive:123", "applied")

    db.upsert_job(conn, _job(title="Backend Engineer (Updated)", match_score=80))

    fetched = db.get_job(conn, "remotive:123")
    assert fetched.status == "applied"
    assert fetched.title == "Backend Engineer (Updated)"
    assert fetched.match_score == 80


def test_boolean_fields_roundtrip(conn):
    db.upsert_job(conn, _job(nigeria_eligible=True, still_open=False))
    fetched = db.get_job(conn, "remotive:123")
    assert fetched.nigeria_eligible is True
    assert fetched.still_open is False


def test_list_jobs_filters_by_status(conn):
    db.upsert_job(conn, _job())
    db.upsert_job(conn, _job(job_id="remotive:456", status="dismissed"))

    new_jobs = db.list_jobs(conn, status="new")
    assert [j.job_id for j in new_jobs] == ["remotive:123"]


def test_list_jobs_filters_by_min_score(conn):
    db.upsert_job(conn, _job(match_score=90))
    db.upsert_job(conn, _job(job_id="remotive:456", match_score=40))

    strong_matches = db.list_jobs(conn, min_score=50)
    assert [j.job_id for j in strong_matches] == ["remotive:123"]


def test_list_jobs_orders_by_score_descending_by_default(conn):
    db.upsert_job(conn, _job(match_score=40))
    db.upsert_job(conn, _job(job_id="remotive:456", match_score=90))

    ordered = db.list_jobs(conn)
    assert [j.job_id for j in ordered] == ["remotive:456", "remotive:123"]


def test_list_jobs_rejects_invalid_order_by(conn):
    with pytest.raises(ValueError):
        db.list_jobs(conn, order_by="job_id; DROP TABLE jobs")


def test_update_status_persists(conn):
    db.upsert_job(conn, _job())
    db.update_status(conn, "remotive:123", "dismissed")
    assert db.get_job(conn, "remotive:123").status == "dismissed"
