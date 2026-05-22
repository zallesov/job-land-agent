from unittest.mock import patch
from scripts.pipeline.types import HermesResult
from scripts.db import get_connection


def _insert_job(con, status="enriched", description="We need a senior Python engineer..."):
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status, title, description) VALUES (?,?,?,?,?)",
        ("http://x.com", "gh", status, "Senior Python Engineer", description)
    ).lastrowid
    con.commit()
    return jid


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
def test_strong_apply_sets_screened_and_writes_assessment(mock_hermes, db_path, con):
    mock_hermes.return_value = STRONG_APPLY_RESULT
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    result = screen_job(jid, db_path=db_path)
    assert result.success is True
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "screened"
    assessment = con.execute("SELECT * FROM job_assessments WHERE job_id = ?", (jid,)).fetchone()
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
def test_skip_verdict_still_sets_screened_status(mock_hermes, db_path, con):
    mock_hermes.return_value = SKIP_RESULT
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid, db_path=db_path)
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "screened"
    assessment = con.execute("SELECT apply_verdict FROM job_assessments WHERE job_id = ?", (jid,)).fetchone()
    assert assessment["apply_verdict"] == "Skip"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_hermes_failure_sets_screen_failed(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="timeout", raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid, db_path=db_path)
    row = con.execute("SELECT status, comment FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "screen_failed"
    assert row["comment"] == "timeout"


@patch("scripts.pipeline.screen_job.hermes_call")
def test_upsert_does_not_duplicate_assessment(mock_hermes, db_path, con):
    mock_hermes.return_value = STRONG_APPLY_RESULT
    jid = _insert_job(con)
    from scripts.pipeline.screen_job import screen_job
    screen_job(jid, db_path=db_path)
    screen_job(jid, db_path=db_path)
    count = con.execute("SELECT COUNT(*) FROM job_assessments WHERE job_id = ?", (jid,)).fetchone()[0]
    assert count == 1
