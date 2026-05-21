from unittest.mock import patch, MagicMock
from scripts.pipeline.types import HermesResult
from scripts.db import get_connection


def _insert_job(con, url="http://x.com"):
    jid = con.execute(
        "INSERT INTO jobs (url, provider, status) VALUES (?, 'gh', 'listed')", (url,)
    ).lastrowid
    con.commit()
    return jid


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_success_updates_db(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=True,
        data={"status": "success", "title": "SWE", "description": "Build things.",
              "apply_url": "http://x.com/apply", "salary_range": "100K EUR",
              "date_posted": "2026-05-01"},
        error=None, raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.enrich_job import enrich_job
    result = enrich_job(jid, db_path=db_path)
    assert result.success is True
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "new"
    assert row["title"] == "SWE"
    assert row["description"] == "Build things."
    assert row["salary_range"] == "100K EUR"


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_failure_sets_enrich_failed(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="login wall", raw_output="",
    )
    jid = _insert_job(con)
    from scripts.pipeline.enrich_job import enrich_job
    result = enrich_job(jid, db_path=db_path)
    assert result.success is False
    row = con.execute("SELECT status, comment FROM jobs WHERE id = ?", (jid,)).fetchone()
    assert row["status"] == "enrich_failed"
    assert row["comment"] == "login wall"


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_hermes_context_includes_url_and_cv(mock_hermes, db_path, con):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="x", raw_output=""
    )
    jid = _insert_job(con, url="http://job.com")
    from scripts.pipeline.enrich_job import enrich_job
    enrich_job(jid, db_path=db_path)
    call_args = mock_hermes.call_args
    assert call_args[0][0] == "enrich-job"
    ctx = call_args[0][1]
    assert ctx["job_id"] == jid
    assert ctx["url"] == "http://job.com"
    assert "cv_path" in ctx
