from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

from job_hunter.models import Job

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    remote_type TEXT NOT NULL DEFAULT 'unclear',
    nigeria_eligible INTEGER,
    salary_min REAL,
    salary_max REAL,
    salary_currency TEXT,
    posted_date TEXT,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    still_open INTEGER,
    match_score INTEGER,
    match_reason TEXT,
    status TEXT NOT NULL DEFAULT 'new'
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


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def _job_to_row(job: Job) -> dict:
    row = job.model_dump(mode="json")
    row["nigeria_eligible"] = job.nigeria_eligible if job.nigeria_eligible is None else int(job.nigeria_eligible)
    row["still_open"] = job.still_open if job.still_open is None else int(job.still_open)
    return row


def _row_to_job(row: sqlite3.Row) -> Job:
    data = dict(row)
    data["nigeria_eligible"] = data["nigeria_eligible"] if data["nigeria_eligible"] is None else bool(data["nigeria_eligible"])
    data["still_open"] = data["still_open"] if data["still_open"] is None else bool(data["still_open"])
    return Job.model_validate(data)


def upsert_job(conn: sqlite3.Connection, job: Job) -> None:
    """Insert a job, or update it while preserving its existing `status`.

    `status` tracks your own review decisions (applied/dismissed/reviewed) and
    must survive across runs, so a re-scored job never silently resets back to
    'new' just because it was seen again in a later search.
    """
    row = _job_to_row(job)
    columns = ["job_id", "status", *_UPDATABLE_COLUMNS]
    placeholders = ", ".join(f":{c}" for c in columns)
    update_clause = ", ".join(f"{c} = :{c}" for c in _UPDATABLE_COLUMNS)
    conn.execute(
        f"""
        INSERT INTO jobs ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT(job_id) DO UPDATE SET {update_clause}
        """,
        row,
    )
    conn.commit()


def upsert_jobs(conn: sqlite3.Connection, jobs: Sequence[Job]) -> None:
    for job in jobs:
        upsert_job(conn, job)


def get_job(conn: sqlite3.Connection, job_id: str) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


_SORTABLE_COLUMNS = {"match_score", "source", "posted_date", "company", "title"}


def list_jobs(
    conn: sqlite3.Connection,
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
        query += " AND status = ?"
        params.append(status)
    if source is not None:
        query += " AND source = ?"
        params.append(source)
    if min_score is not None:
        query += " AND match_score >= ?"
        params.append(min_score)
    query += f" ORDER BY {order_by}"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_job(row) for row in rows]


def update_status(conn: sqlite3.Connection, job_id: str, status: str) -> None:
    conn.execute("UPDATE jobs SET status = ? WHERE job_id = ?", (status, job_id))
    conn.commit()
