import os

import pytest

from job_hunter import db
from job_hunter.models import Job


@pytest.fixture
def conn():
    """A real Postgres connection, truncated clean before each test.

    db.py targets Postgres (Neon in production) now, not SQLite, so there's
    no in-memory stand-in. These tests need TEST_DATABASE_URL pointed at a
    real (ideally disposable/free-tier) Postgres instance - set it in .env
    for local runs. Skips gracefully wherever it isn't configured, rather
    than failing confusingly against a missing database.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set - skipping tests that need a real Postgres instance.")
    connection = db.get_connection(url)
    connection.execute("TRUNCATE TABLE jobs")
    connection.execute("TRUNCATE TABLE profile")
    connection.commit()
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


def test_get_cv_bytes_returns_none_when_unset(conn):
    assert db.get_cv_bytes(conn) is None


def test_save_and_get_cv_bytes_roundtrips(conn):
    db.save_cv_bytes(conn, b"%PDF-1.4 fake cv content", filename="CV.pdf")
    assert db.get_cv_bytes(conn) == b"%PDF-1.4 fake cv content"


def test_save_cv_bytes_overwrites_previous(conn):
    db.save_cv_bytes(conn, b"old cv")
    db.save_cv_bytes(conn, b"new cv")
    assert db.get_cv_bytes(conn) == b"new cv"


def test_get_preferences_returns_empty_dict_when_unset(conn):
    assert db.get_preferences(conn) == {}


def test_save_and_get_preferences_roundtrips(conn):
    prefs = {"role_titles": ["Backend Engineer"], "actual_years_experience": 2, "nigeria_required": True}
    db.save_preferences(conn, prefs)
    assert db.get_preferences(conn) == prefs


def test_save_preferences_overwrites_previous(conn):
    db.save_preferences(conn, {"role_titles": ["A"]})
    db.save_preferences(conn, {"role_titles": ["B"]})
    assert db.get_preferences(conn) == {"role_titles": ["B"]}


def test_distinct_sources_returns_sorted_unique_sources(conn):
    db.upsert_job(conn, _job(job_id="remotive:1", source="remotive"))
    db.upsert_job(conn, _job(job_id="wwr:1", source="wwr"))
    db.upsert_job(conn, _job(job_id="remotive:2", source="remotive"))
    assert db.distinct_sources(conn) == ["remotive", "wwr"]
