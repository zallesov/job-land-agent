from unittest.mock import patch
from scripts.pipeline.types import HermesResult


def _insert_job(mcp, url="http://x.com"):
    rec = mcp.create("jobs", {"url": url, "provider": "gh", "status": "listed"})
    return rec["id"]


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_success_updates_db(mock_hermes, mcp):
    mock_hermes.return_value = HermesResult(
        success=True,
        data={"status": "success", "title": "SWE", "description": "Build things.",
              "apply_url": "http://x.com/apply", "salary_range": "100K EUR",
              "date_posted": "2026-05-01"},
        error=None, raw_output="",
    )
    jid = _insert_job(mcp)
    from scripts.pipeline.enrich_job import enrich_job
    result = enrich_job(jid)
    assert result.success is True
    row = mcp.get("jobs", jid)
    assert row["status"] == "new"
    assert row["title"] == "SWE"
    assert row["description"] == "Build things."
    assert row["salary_range"] == "100K EUR"


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_failure_sets_enrich_failed(mock_hermes, mcp):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="login wall", raw_output="",
    )
    jid = _insert_job(mcp)
    from scripts.pipeline.enrich_job import enrich_job
    result = enrich_job(jid)
    assert result.success is False
    row = mcp.get("jobs", jid)
    assert row["status"] == "enrich_failed"
    assert row["comment"] == "login wall"


@patch("scripts.pipeline.enrich_job.hermes_call")
def test_hermes_context_includes_url_and_cv(mock_hermes, mcp):
    mock_hermes.return_value = HermesResult(
        success=False, data={}, error="x", raw_output=""
    )
    jid = _insert_job(mcp, url="http://job.com")
    from scripts.pipeline.enrich_job import enrich_job
    enrich_job(jid)
    call_args = mock_hermes.call_args
    assert call_args[0][0] == "enrich-job"
    ctx = call_args[0][1]
    assert ctx["job_id"] == jid
    assert ctx["url"] == "http://job.com"
    assert "cv_path" in ctx
