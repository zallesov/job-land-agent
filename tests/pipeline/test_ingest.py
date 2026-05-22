import sqlite3
from scripts.pipeline.types import ShallowJob
from scripts.pipeline.ingest import ingest_jobs
from scripts.db import get_connection


def _job(url="http://x.com", company="Acme", title="SWE"):
    return ShallowJob(
        provider="greenhouse", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date="2026-05-01", salary_raw="90K EUR",
    )


def test_ingest_returns_ids(db_path):
    jobs = [_job("http://a.com", "A", "E1"), _job("http://b.com", "B", "E2")]
    ids = ingest_jobs(jobs, db_path=db_path)
    assert len(ids) == 2
    assert all(isinstance(i, int) for i in ids)


def test_ingest_sets_status_new(db_path, con):
    ids = ingest_jobs([_job()], db_path=db_path)
    row = con.execute("SELECT status, dedup_key FROM jobs WHERE id = ?", (ids[0],)).fetchone()
    assert row["status"] == "new"
    assert row["dedup_key"] == "Acme::SWE"


def test_ingest_stores_all_fields(db_path, con):
    ids = ingest_jobs([_job()], db_path=db_path)
    row = con.execute("SELECT * FROM jobs WHERE id = ?", (ids[0],)).fetchone()
    assert row["provider"] == "greenhouse"
    assert row["posted_company_name"] == "Acme"
    assert row["title"] == "SWE"
    assert row["date_posted"] == "2026-05-01"
    assert row["salary_range"] == "90K EUR"


def test_ingest_empty_list(db_path):
    ids = ingest_jobs([], db_path=db_path)
    assert ids == []
