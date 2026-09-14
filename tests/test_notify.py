from job_hunter.models import Job
from job_hunter.notify import filter_new_strong_matches, send_digest


def _job(job_id="remotive:1", **overrides) -> Job:
    fields = {
        "job_id": job_id,
        "title": "Backend Engineer",
        "company": "Acme",
        "source": "remotive",
        "url": "https://example.com",
        "match_score": 85,
        "match_reason": "Strong fit",
    }
    fields.update(overrides)
    return Job(**fields)


def test_send_digest_calls_send_fn_with_expected_payload():
    calls = []
    send_digest(
        [_job()],
        to_email="me@example.com",
        from_email="bot@example.com",
        api_key="re_fake",
        send_fn=calls.append,
    )
    assert len(calls) == 1
    payload = calls[0]
    assert payload["to"] == ["me@example.com"]
    assert payload["from"] == "bot@example.com"
    assert "1 new strong match found" in payload["subject"]
    assert "Backend Engineer" in payload["html"]
    assert "Acme" in payload["html"]


def test_send_digest_pluralizes_subject_for_multiple_jobs():
    calls = []
    send_digest(
        [_job(job_id="remotive:1"), _job(job_id="remotive:2")],
        to_email="me@example.com",
        api_key="re_fake",
        send_fn=calls.append,
    )
    assert "2 new strong matches found" in calls[0]["subject"]


def test_send_digest_is_noop_with_no_jobs():
    calls = []
    send_digest([], to_email="me@example.com", api_key="re_fake", send_fn=calls.append)
    assert calls == []


def test_send_digest_is_noop_without_api_key():
    calls = []
    send_digest([_job()], to_email="me@example.com", api_key=None, send_fn=calls.append)
    assert calls == []


def test_send_digest_is_noop_without_to_email():
    calls = []
    send_digest([_job()], to_email=None, api_key="re_fake", send_fn=calls.append)
    assert calls == []


def test_send_digest_escapes_html_in_job_fields():
    calls = []
    malicious = _job(title="<script>alert(1)</script>")
    send_digest([malicious], to_email="me@example.com", api_key="re_fake", send_fn=calls.append)
    assert "<script>" not in calls[0]["html"]
    assert "&lt;script&gt;" in calls[0]["html"]


def test_filter_new_strong_matches_excludes_already_seen():
    jobs = [_job(job_id="remotive:1"), _job(job_id="remotive:2")]
    result = filter_new_strong_matches(jobs, previously_seen_ids={"remotive:1"})
    assert [j.job_id for j in result] == ["remotive:2"]


def test_filter_new_strong_matches_excludes_weak_scores():
    jobs = [_job(job_id="remotive:1", match_score=50)]
    result = filter_new_strong_matches(jobs, previously_seen_ids=set())
    assert result == []


def test_filter_new_strong_matches_includes_new_and_strong():
    jobs = [_job(job_id="remotive:1", match_score=90)]
    result = filter_new_strong_matches(jobs, previously_seen_ids=set())
    assert len(result) == 1
