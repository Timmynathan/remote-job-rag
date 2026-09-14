from __future__ import annotations

from datetime import date
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from job_hunter.models import Job

DEFAULT_MAX_CANDIDATES_TO_SCORE = 15


class MatchResult(BaseModel):
    match_score: int = Field(ge=0, le=100)
    match_reason: str


def _default_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0)


def score_job(cv_text: str, job: Job, *, llm: Any = None, actual_years_experience: int | None = None) -> MatchResult:
    llm = llm or _default_llm()
    structured_llm = llm.with_structured_output(MatchResult)
    experience_line = (
        f"Note: the candidate's actual real-world professional experience is about "
        f"{actual_years_experience} year(s), regardless of anything the CV text implies otherwise. "
        "Weigh seniority fit using this actual figure, not the CV's stated one.\n\n"
        if actual_years_experience is not None
        else ""
    )
    prompt = (
        "Judge how well this candidate fits this remote job posting.\n\n"
        f"Candidate CV:\n{cv_text}\n\n"
        f"{experience_line}"
        f"Job title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Description:\n{job.description}\n\n"
        "Give a match_score from 0-100 and a short match_reason explaining "
        "the score in terms of the candidate's actual skills/experience "
        "against this specific posting."
    )
    return structured_llm.invoke(prompt)


def score_node(state: dict) -> dict:
    """Score unscored candidates, capped at `max_candidates_to_score` total for the
    whole run (tracked via `scored_count`, which persists across refine-loop
    iterations) - not per call. This keeps a single run within free-tier LLM
    quotas now that six sources can surface far more candidates than one did.

    Newest postings are prioritized first so a tight budget isn't wasted on
    stale listings that happened to merge in earlier.
    """
    llm = state.get("llm")
    actual_years_experience = state.get("preferences", {}).get("actual_years_experience")
    max_to_score = state.get("max_candidates_to_score", DEFAULT_MAX_CANDIDATES_TO_SCORE)
    already_scored = state.get("scored_count", 0)
    budget = max(max_to_score - already_scored, 0)

    unscored = [job for job in state["candidates"] if job.match_score is None]
    unscored.sort(key=lambda job: job.posted_date or date.min, reverse=True)

    newly_scored = 0
    for job in unscored[:budget]:
        result = score_job(state["cv_text"], job, llm=llm, actual_years_experience=actual_years_experience)
        job.match_score = result.match_score
        job.match_reason = result.match_reason
        newly_scored += 1

    return {"candidates": state["candidates"], "scored_count": already_scored + newly_scored}
