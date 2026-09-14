from __future__ import annotations

STRONG_MATCH_THRESHOLD = 70


def should_refine(state: dict) -> str:
    strong = [j for j in state["candidates"] if (j.match_score or 0) >= STRONG_MATCH_THRESHOLD]
    min_strong = state.get("min_strong_matches", 5)
    max_iterations = state.get("max_iterations", 2)
    if len(strong) >= min_strong or state.get("iteration", 1) >= max_iterations:
        return "finish"
    return "refine"
