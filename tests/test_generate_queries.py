from job_hunter.nodes.generate_queries import QueryList, generate_queries, generate_queries_node
from tests.conftest import FakeLLM


def test_generate_queries_returns_llm_output():
    llm = FakeLLM(QueryList(queries=["backend engineer", "python developer"]))
    result = generate_queries("Some CV text", {"role_titles": ["Backend Engineer"]}, llm=llm)
    assert result == ["backend engineer", "python developer"]


def test_generate_queries_node_increments_iteration_from_zero():
    llm = FakeLLM(QueryList(queries=["backend engineer"]))
    state = {"cv_text": "CV", "preferences": {}, "llm": llm}
    result = generate_queries_node(state)
    assert result["iteration"] == 1
    assert result["queries"] == ["backend engineer"]


def test_generate_queries_node_increments_iteration_on_retry():
    llm = FakeLLM(QueryList(queries=["software engineer"]))
    state = {"cv_text": "CV", "preferences": {}, "iteration": 1, "llm": llm}
    result = generate_queries_node(state)
    assert result["iteration"] == 2
