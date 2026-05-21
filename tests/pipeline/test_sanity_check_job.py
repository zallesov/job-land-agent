from unittest.mock import patch
from scripts.pipeline.types import HermesResult
from scripts.db import get_connection


def _insert_job(con, status="new"):
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES ('http://x.com','gh',?)", (status,)
    ).lastrowid
    con.commit()
    return jid


@patch("scripts.pipeline.sanity_check_job.hermes_call")
def test_pass_leaves_status_new(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=True, data={"status": "success", "verdict": "pass", "reason": "Good fit"},
        error=None, raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.sanity_check_job import sanity_check_job
    result = sanity_check_job(jid, db_path=db_path)
    assert result.success is True
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "new"


@patch("scripts.pipeline.sanity_check_job.hermes_call")
def test_skip_sets_not_interested(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=True,
        data={"status": "success", "verdict": "skip", "reason": "On-site only"},
        error=None, raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.sanity_check_job import sanity_check_job
    sanity_check_job(jid, db_path=db_path)
    row = con.execute("SELECT status, comment FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "not_interested"
    assert row["comment"] == "On-site only"


@patch("scripts.pipeline.sanity_check_job.hermes_call")
def test_hermes_failure_sets_sanity_failed(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="could not load job description", raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.sanity_check_job import sanity_check_job
    sanity_check_job(jid, db_path=db_path)
    row = con.execute("SELECT status FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "sanity_failed"
