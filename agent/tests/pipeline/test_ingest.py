from scripts.pipeline.types import ShallowJob
from scripts.pipeline.ingest import ingest_jobs


def _job(url="http://x.com", company="Acme", title="SWE"):
    return ShallowJob(
        provider="greenhouse", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date="2026-05-01", salary_raw="90K EUR",
    )


def test_ingest_returns_ids(mcp):
    jobs = [_job("http://a.com", "A", "E1"), _job("http://b.com", "B", "E2")]
    ids = ingest_jobs(jobs)
    assert len(ids) == 2
    assert all(isinstance(i, str) for i in ids)


def test_ingest_sets_status_new(mcp):
    ids = ingest_jobs([_job()])
    row = mcp.get("jobs", ids[0])
    assert row["status"] == "new"
    assert row["dedup_key"] == "Acme::SWE"
    # single state field — pipeline_status must never be written
    assert "pipeline_status" not in row


def test_ingest_skip_job_gets_skip_status(mcp):
    skip_job = _job("http://skip.com", "Skipco", "Skipped")
    skip_job.status = "skip"
    ingest_jobs([skip_job])
    row = mcp.find_job_by_url("http://skip.com")
    assert row["status"] == "skip"
    assert "pipeline_status" not in row


def test_ingest_stores_all_fields(mcp):
    ids = ingest_jobs([_job()])
    row = mcp.get("jobs", ids[0])
    assert row["provider"] == "greenhouse"
    assert row["posted_company_name"] == "Acme"
    assert row["title"] == "SWE"
    assert row["date_posted"] == "2026-05-01"
    assert row["salary_range"] == "90K EUR"


def test_ingest_empty_list(mcp):
    ids = ingest_jobs([])
    assert ids == []


def test_ingest_skip_status_excluded_from_ids(mcp):
    skip_job = _job("http://skip.com", "Skipco", "Skipped")
    skip_job.status = "skip"
    ids = ingest_jobs([skip_job, _job()])
    assert len(ids) == 1
