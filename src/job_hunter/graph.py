from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from job_hunter.models import Job
from job_hunter.nodes.generate_queries import generate_queries_node
from job_hunter.nodes.refine import should_refine
from job_hunter.nodes.retrieve import retrieve_node
from job_hunter.nodes.score import score_node
from job_hunter.nodes.validate_dedupe import validate_dedupe_node


class HuntState(TypedDict, total=False):
    cv_text: str
    preferences: dict
    queries: list[str]
    candidates: list[Job]
    iteration: int
    max_iterations: int
    min_strong_matches: int
    max_candidates_to_score: int
    scored_count: int
    llm: Any
    http_client: Any


def build_graph():
    graph = StateGraph(HuntState)
    graph.add_node("generate_queries", generate_queries_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("validate_dedupe", validate_dedupe_node)
    graph.add_node("score", score_node)

    graph.set_entry_point("generate_queries")
    graph.add_edge("generate_queries", "retrieve")
    graph.add_edge("retrieve", "validate_dedupe")
    graph.add_edge("validate_dedupe", "score")
    graph.add_conditional_edges("score", should_refine, {"refine": "generate_queries", "finish": END})

    return graph.compile()
