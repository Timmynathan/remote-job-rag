from job_hunter.models import Job
from job_hunter.nodes.refine import should_refine


def _job(score: int | None) -> Job:
    return Job(
        job_id=f"remotive:{score}",
        title="Backend Engineer",
        company="Acme",
        source="remotive",
        url="https://example.com",
        match_score=score,
    )


def test_finishes_when_enough_strong_matches():
    state = {
        "candidates": [_job(90), _job(80)],
        "min_strong_matches": 2,
        "max_iterations": 2,
        "iteration": 1,
    }
    assert should_refine(state) == "finish"


def test_refines_when_not_enough_strong_matches_and_iterations_remain():
    state = {
        "candidates": [_job(40)],
        "min_strong_matches": 2,
        "max_iterations": 2,
        "iteration": 1,
    }
    assert should_refine(state) == "refine"


def test_finishes_when_max_iterations_reached_even_with_weak_matches():
    state = {
        "candidates": [_job(40)],
        "min_strong_matches": 2,
        "max_iterations": 2,
        "iteration": 2,
    }
    assert should_refine(state) == "finish"


def test_treats_missing_score_as_zero():
    state = {
        "candidates": [_job(None)],
        "min_strong_matches": 1,
        "max_iterations": 2,
        "iteration": 1,
    }
    assert should_refine(state) == "refine"
