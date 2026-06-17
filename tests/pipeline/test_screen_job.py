from unittest.mock import patch
from scripts.pipeline.types import HermesResult


def _insert_job(pb, status="enriched", description="We need a senior Python engineer..."):
    rec = pb.create("jobs", {
        "url": "http://x.com", "provider": "gh", "status": status,
        "title": "Senior Python Engineer", "description": description,
    })
    return rec["id"]


STRONG_APPLY_RESULT = HermesResult(
    success=True,
    data={
        "status": "success",
        "apply_verdict": "Strong Apply",
        "relevance_score": 90,
        "one_line_summary": "Great fit",
        "seniority_fit": "Senior IC",
        "tech_stack_fit": "Python match",
        "remote_eligibility": "Remote EU",
        "salary_assessment": "€100k",
    },
    error=None, raw_output="",
)

SKIP_RESULT = HermesResult(
    success=True,
    data={
        "status": "success",
        "apply_verdict": "Skip",
        "relevance_score": 5,
        "one_line_summary": "On-site junior role",
        "seniority_fit": "Junior, does not match",
        "tech_stack_fit": "No overlap",
        "remote_eligibility": "On-site only",
        "salary_assessment": "Not disclosed",
    },
    error=None, raw_output="",
)


@patch("scripts.pipeline.screen_job.hermes_call")
def test_strong_apply_sets_screened_and_writes_assessment(mock_hermes, pb):
    mock_hermes.return_value = STRONG_APPLY_RESULT
    jid = _insert_job(pb)
    from scripts.pipeline.screen_job import screen_job
    result = screen_job(jid)
    assert result.success is True
    row = pb.get("jobs", jid)
    assert row["status"] == "screened"
    assessment = pb.get_one("job_assessments", f"job_id='{jid}'")
    assert assessment is not None
    assert assessment["apply_verdict"] == "Strong Apply"
    assert assessment["relevance_score"] == 90
    assert assessment["assessment_status"] == "screened"
    assert assessment["one_line_summary"] == "Great fit"
    assert assessment["seniority_fit"] == "Senior IC"
    assert assessment["tech_stack_fit"] == "Python match"
    assert assessment["remote_eligibility"] == "Remote EU"
    assert assessment["salary_assessment"] == "€100k"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_skip_verdict_still_sets_screened_status(mock_hermes, pb):
    mock_hermes.return_value = SKIP_RESULT
    jid = _insert_job(pb)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid)
    row = pb.get("jobs", jid)
    assert row["status"] == "screened"
    assessment = pb.get_one("job_assessments", f"job_id='{jid}'")
    assert assessment["apply_verdict"] == "Skip"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_hermes_failure_sets_screen_failed(mock_hermes, pb):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="timeout", raw_output="",
    )
    jid = _insert_job(pb)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid)
    row = pb.get("jobs", jid)
    assert row["status"] == "screen_failed"
    assert row["comment"] == "timeout"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_upsert_does_not_duplicate_assessment(mock_hermes, pb):
    mock_hermes.return_value = STRONG_APPLY_RESULT
    jid = _insert_job(pb)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid)
    screen_job(jid)
    count = sum(1 for r in pb.collections.get("job_assessments", {}).values() if r["job_id"] == jid)
    assert count == 1
