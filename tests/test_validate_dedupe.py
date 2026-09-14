from job_hunter.models import Job
from job_hunter.nodes.validate_dedupe import validate_dedupe_node


def _job(**overrides) -> Job:
    fields = {
        "job_id": "remotive:1",
        "title": "Backend Engineer",
        "company": "Acme",
        "source": "remotive",
        "url": "https://example.com",
    }
    fields.update(overrides)
    return Job(**fields)


def test_sets_still_open_true_when_unset():
    state = {"candidates": [_job()]}
    result = validate_dedupe_node(state)
    assert result["candidates"][0].still_open is True


def test_does_not_override_existing_still_open_value():
    state = {"candidates": [_job(still_open=False)]}
    result = validate_dedupe_node(state)
    assert result["candidates"][0].still_open is False


def test_drops_geographically_ineligible_job_by_default():
    state = {"candidates": [_job(nigeria_eligible=False)]}
    result = validate_dedupe_node(state)
    assert result["candidates"] == []


def test_keeps_geographically_ineligible_job_when_not_required():
    state = {
        "candidates": [_job(nigeria_eligible=False)],
        "preferences": {"nigeria_required": False},
    }
    result = validate_dedupe_node(state)
    assert len(result["candidates"]) == 1


def test_keeps_job_with_unclear_eligibility():
    state = {"candidates": [_job(nigeria_eligible=None)]}
    result = validate_dedupe_node(state)
    assert len(result["candidates"]) == 1


def test_drops_senior_titles_by_default():
    state = {"candidates": [_job(title="Senior Backend Engineer")]}
    result = validate_dedupe_node(state)
    assert result["candidates"] == []


def test_drops_other_default_seniority_keywords():
    titles = ["Staff Engineer", "Principal Engineer", "Engineering Lead", "Director of Engineering"]
    state = {"candidates": [_job(job_id=f"remotive:{i}", title=t) for i, t in enumerate(titles)]}
    result = validate_dedupe_node(state)
    assert result["candidates"] == []


def test_keeps_matching_role_when_preferences_set():
    state = {
        "candidates": [_job(title="Full Stack Engineer")],
        "preferences": {"role_titles": ["Full Stack Engineer", "Frontend Engineer", "Backend Engineer", "AI Engineer"]},
    }
    result = validate_dedupe_node(state)
    assert len(result["candidates"]) == 1


def test_drops_off_target_role_when_preferences_set():
    state = {
        "candidates": [_job(title="Business Development Representative")],
        "preferences": {"role_titles": ["Full Stack Engineer", "Frontend Engineer", "Backend Engineer", "AI Engineer"]},
    }
    result = validate_dedupe_node(state)
    assert result["candidates"] == []


def test_matches_ai_engineer_synonyms():
    state = {
        "candidates": [_job(title="Machine Learning Engineer")],
        "preferences": {"role_titles": ["AI Engineer"]},
    }
    result = validate_dedupe_node(state)
    assert len(result["candidates"]) == 1


def test_no_role_titles_keeps_everything():
    state = {"candidates": [_job(title="Business Development Representative")], "preferences": {}}
    result = validate_dedupe_node(state)
    assert len(result["candidates"]) == 1


def test_custom_exclude_keywords_override_default():
    state = {
        "candidates": [_job(title="Senior Backend Engineer")],
        "preferences": {"exclude_title_keywords": ["contractor"]},
    }
    result = validate_dedupe_node(state)
    assert len(result["candidates"]) == 1
