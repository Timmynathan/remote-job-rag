from __future__ import annotations

_DEFAULT_EXCLUDE_TITLE_KEYWORDS = [
    "senior",
    "sr.",
    "staff",
    "principal",
    "lead",
    "director",
    "head of",
    "vp ",
    "chief",
]

_AI_ROLE_SYNONYMS = ("ai engineer", "machine learning engineer", "ml engineer", "ai/ml", "artificial intelligence")


def _normalize(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _matches_role(title: str, role_titles: list[str]) -> bool:
    if not role_titles:
        return True
    normalized_title = _normalize(title)
    for role in role_titles:
        normalized_role = _normalize(role)
        if normalized_role and (normalized_role in normalized_title or normalized_title in normalized_role):
            return True
        if "ai" in normalized_role and "engineer" in normalized_role:
            if any(synonym in title.lower() for synonym in _AI_ROLE_SYNONYMS):
                return True
    return False


def _matches_seniority_exclusion(title: str, exclude_keywords: list[str]) -> bool:
    lowered = title.lower()
    return any(keyword.lower() in lowered for keyword in exclude_keywords)


def validate_dedupe_node(state: dict) -> dict:
    """Mark still-open status, then drop candidates that don't actually fit.

    Cross-posting dedup already happens in `retrieve_node` (merge by job_id),
    since Remotive is currently the only source. Liveness is set directly to
    True here because Remotive's API reflects current listings - a Playwright
    liveness check is only needed for search-index sources (LinkedIn/Indeed/
    Glassdoor) once those are added, per project-about.md §3.

    Filtering (geo eligibility, role match, seniority exclusion) happens here
    rather than just being reflected in the match_score, so irrelevant
    postings never reach the LLM scoring step at all - cheaper, and keeps the
    dashboard free of obvious non-fits.
    """
    preferences = state.get("preferences", {})
    role_titles = preferences.get("role_titles") or []
    exclude_keywords = preferences.get("exclude_title_keywords", _DEFAULT_EXCLUDE_TITLE_KEYWORDS)
    nigeria_required = preferences.get("nigeria_required", True)

    kept = []
    for job in state["candidates"]:
        if job.still_open is None:
            job.still_open = True

        if nigeria_required and job.nigeria_eligible is False:
            continue
        if _matches_seniority_exclusion(job.title, exclude_keywords):
            continue
        if not _matches_role(job.title, role_titles):
            continue

        kept.append(job)

    return {"candidates": kept}
