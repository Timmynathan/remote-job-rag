from __future__ import annotations

from collections.abc import Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from job_hunter.models import Job

_JOBS_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    remote_type TEXT NOT NULL DEFAULT 'unclear',
    nigeria_eligible BOOLEAN,
    salary_min DOUBLE PRECISION,
    salary_max DOUBLE PRECISION,
    salary_currency TEXT,
    posted_date DATE,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    still_open BOOLEAN,
    match_score INTEGER,
    match_reason TEXT,
    status TEXT NOT NULL DEFAULT 'new'
);
"""

_PROFILE_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id TEXT PRIMARY KEY DEFAULT 'default',
    cv_bytes BYTEA,
    cv_filename TEXT,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

_UPDATABLE_COLUMNS = [
    "title",
    "company",
    "location",
    "remote_type",
    "nigeria_eligible",
    "salary_min",
    "salary_max",
    "salary_currency",
    "posted_date",
    "source",
    "url",
    "description",
    "still_open",
    "match_score",
    "match_reason",
]


def get_connection(database_url: str) -> psycopg.Connection:
    conn = psycopg.connect(database_url, row_factory=dict_row, autocommit=False)
    conn.execute(_JOBS_SCHEMA)
    conn.execute(_PROFILE_SCHEMA)
    conn.commit()
    return conn


def _job_to_row(job: Job) -> dict:
    return job.model_dump()


def _row_to_job(row: dict) -> Job:
    return Job.model_validate(dict(row))


def upsert_job(conn: psycopg.Connection, job: Job) -> None:
    """Insert a job, or update it while preserving its existing `status`.

    `status` tracks your own review decisions (applied/dismissed/reviewed) and
    must survive across runs, so a re-scored job never silently resets back to
    'new' just because it was seen again in a later search.
    """
    row = _job_to_row(job)
    columns = ["job_id", "status", *_UPDATABLE_COLUMNS]
    placeholders = ", ".join(f"%({c})s" for c in columns)
    update_clause = ", ".join(f"{c} = %({c})s" for c in _UPDATABLE_COLUMNS)
    conn.execute(
        f"""
        INSERT INTO jobs ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (job_id) DO UPDATE SET {update_clause}
        """,
        row,
    )
    conn.commit()


def upsert_jobs(conn: psycopg.Connection, jobs: Sequence[Job]) -> None:
    for job in jobs:
        upsert_job(conn, job)


def get_job(conn: psycopg.Connection, job_id: str) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


_SORTABLE_COLUMNS = {"match_score", "source", "posted_date", "company", "title"}


def list_jobs(
    conn: psycopg.Connection,
    *,
    status: str | None = None,
    source: str | None = None,
    min_score: int | None = None,
    order_by: str = "match_score DESC",
) -> list[Job]:
    column, _, direction = order_by.partition(" ")
    direction = direction.upper() or "DESC"
    if column not in _SORTABLE_COLUMNS or direction not in {"ASC", "DESC"}:
        raise ValueError(f"Invalid order_by: {order_by!r}")
    order_by = f"{column} {direction}"

    query = "SELECT * FROM jobs WHERE 1=1"
    params: list = []
    if status is not None:
        query += " AND status = %s"
        params.append(status)
    if source is not None:
        query += " AND source = %s"
        params.append(source)
    if min_score is not None:
        query += " AND match_score >= %s"
        params.append(min_score)
    query += f" ORDER BY {order_by}"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_job(row) for row in rows]


def update_status(conn: psycopg.Connection, job_id: str, status: str) -> None:
    conn.execute("UPDATE jobs SET status = %s WHERE job_id = %s", (status, job_id))
    conn.commit()


def distinct_sources(conn: psycopg.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT source FROM jobs ORDER BY source").fetchall()
    return [row["source"] for row in rows]


# --- CV + preferences: single shared "profile" row, so local agent runs and
# the hosted dashboard both read/write the exact same data (project-about.md
# §4/§9). ---


def get_cv_bytes(conn: psycopg.Connection) -> bytes | None:
    row = conn.execute("SELECT cv_bytes FROM profile WHERE id = 'default'").fetchone()
    if not row or row["cv_bytes"] is None:
        return None
    return bytes(row["cv_bytes"])


def save_cv_bytes(conn: psycopg.Connection, cv_bytes: bytes, *, filename: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO profile (id, cv_bytes, cv_filename)
        VALUES ('default', %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            cv_bytes = EXCLUDED.cv_bytes,
            cv_filename = EXCLUDED.cv_filename,
            updated_at = now()
        """,
        (cv_bytes, filename),
    )
    conn.commit()


def get_preferences(conn: psycopg.Connection) -> dict:
    row = conn.execute("SELECT preferences FROM profile WHERE id = 'default'").fetchone()
    if not row or row["preferences"] is None:
        return {}
    return row["preferences"]


def save_preferences(conn: psycopg.Connection, preferences: dict) -> None:
    conn.execute(
        """
        INSERT INTO profile (id, preferences)
        VALUES ('default', %s)
        ON CONFLICT (id) DO UPDATE SET
            preferences = EXCLUDED.preferences,
            updated_at = now()
        """,
        (Jsonb(preferences),),
    )
    conn.commit()
