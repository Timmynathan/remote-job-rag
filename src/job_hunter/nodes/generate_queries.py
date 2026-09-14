from __future__ import annotations

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel


class QueryList(BaseModel):
    queries: list[str]


def _default_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)


def generate_queries(
    cv_text: str,
    preferences: dict,
    *,
    broaden: bool = False,
    llm: Any = None,
) -> list[str]:
    """Use Gemini to turn a CV + preferences into a handful of Remotive search queries."""
    llm = llm or _default_llm()
    structured_llm = llm.with_structured_output(QueryList)

    instruction = (
        "Broaden the search: use fewer, more general keywords so more postings match, "
        "while staying strictly within the target roles below."
        if broaden
        else "Use specific, targeted keywords that closely match the candidate's background."
    )
    role_titles = preferences.get("role_titles")
    role_line = (
        f"Search ONLY for these role types, nothing else: {', '.join(role_titles)}.\n" if role_titles else ""
    )
    actual_years = preferences.get("actual_years_experience")
    experience_line = (
        f"The candidate's actual real-world professional experience is about {actual_years} year(s), "
        "regardless of anything the CV text implies otherwise - do not search for senior-level roles.\n"
        if actual_years is not None
        else ""
    )
    prompt = (
        "You are helping search Remotive.com for remote jobs open to a candidate based in Nigeria.\n\n"
        f"Candidate CV:\n{cv_text}\n\n"
        f"Stated preferences: {preferences}\n\n"
        f"{role_line}"
        f"{experience_line}"
        f"{instruction}\n"
        "Produce 3-5 short search-query strings (keywords only, no full sentences) "
        "suitable for a job board's free-text search box."
    )
    result: QueryList = structured_llm.invoke(prompt)
    return result.queries


def generate_queries_node(state: dict) -> dict:
    iteration = state.get("iteration", 0) + 1
    queries = generate_queries(
        state["cv_text"],
        state["preferences"],
        broaden=iteration > 1,
        llm=state.get("llm"),
    )
    return {"queries": queries, "iteration": iteration}
