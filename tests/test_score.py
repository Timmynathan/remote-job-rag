from job_hunter.models import Job
from job_hunter.nodes.score import MatchResult, score_job, score_node
from tests.conftest import FakeLLM


def _job(job_id="remotive:1", **overrides) -> Job:
    fields = {
        "job_id": job_id,
        "title": "Backend Engineer",
        "company": "Acme",
        "source": "remotive",
        "url": "https://example.com",
        "description": "Build APIs in Python.",
    }
    fields.update(overrides)
    return Job(**fields)


def test_score_job_returns_llm_result():
    llm = FakeLLM(MatchResult(match_score=85, match_reason="Strong Python background"))
    result = score_job("CV mentioning Python", _job(), llm=llm)
    assert result.match_score == 85
    assert result.match_reason == "Strong Python background"


def test_score_node_sets_score_and_reason_on_job():
    llm = FakeLLM(MatchResult(match_score=72, match_reason="Good fit"))
    state = {"cv_text": "CV", "candidates": [_job()], "llm": llm}
    result = score_node(state)
    job = result["candidates"][0]
    assert job.match_score == 72
    assert job.match_reason == "Good fit"


def test_score_node_skips_already_scored_jobs():
    llm = FakeLLM(MatchResult(match_score=99, match_reason="Should not be called"))
    already_scored = _job(match_score=50, match_reason="Previous run")
    state = {"cv_text": "CV", "candidates": [already_scored], "llm": llm}
    result = score_node(state)
    assert result["candidates"][0].match_score == 50
    assert result["candidates"][0].match_reason == "Previous run"


def test_score_node_respects_max_candidates_to_score():
    llm = FakeLLM(MatchResult(match_score=70, match_reason="Fit"))
    jobs = [_job(job_id=f"remotive:{i}") for i in range(5)]
    state = {"cv_text": "CV", "candidates": jobs, "llm": llm, "max_candidates_to_score": 2}

    result = score_node(state)

    scored = [j for j in result["candidates"] if j.match_score is not None]
    assert len(scored) == 2
    assert result["scored_count"] == 2


def test_score_node_prioritizes_newest_postings_within_budget():
    llm = FakeLLM(MatchResult(match_score=70, match_reason="Fit"))
    old_job = _job(job_id="remotive:old", posted_date="2020-01-01")
    new_job = _job(job_id="remotive:new", posted_date="2026-09-01")
    state = {"cv_text": "CV", "candidates": [old_job, new_job], "llm": llm, "max_candidates_to_score": 1}

    result = score_node(state)

    scored_ids = {j.job_id for j in result["candidates"] if j.match_score is not None}
    assert scored_ids == {"remotive:new"}


def test_score_node_accumulates_scored_count_across_calls():
    llm = FakeLLM(MatchResult(match_score=70, match_reason="Fit"))
    jobs = [_job(job_id=f"remotive:{i}") for i in range(3)]
    state = {"cv_text": "CV", "candidates": jobs, "llm": llm, "max_candidates_to_score": 5, "scored_count": 4}

    result = score_node(state)

    # budget = max(5 - 4, 0) = 1, so only 1 of the 3 unscored jobs gets scored.
    assert result["scored_count"] == 5
