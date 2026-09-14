from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

RemoteType = Literal["fully_remote", "hybrid", "unclear"]
JobStatus = Literal["new", "reviewed", "applied", "dismissed"]


class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: str | None = None
    remote_type: RemoteType = "unclear"
    nigeria_eligible: bool | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    posted_date: date | None = None
    source: str
    url: str
    description: str = ""
    still_open: bool | None = None
    match_score: int | None = Field(default=None, ge=0, le=100)
    match_reason: str | None = None
    status: JobStatus = "new"

