import pytest
from scripts.pipeline.types import ShallowJob
from scripts.pipeline.dedup import dedup_jobs
from scripts.db import get_connection


def _job(company="Acme", title="SWE", url="http://x.com"):
    return ShallowJob(
        provider="test", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date=None, salary_raw=None,
    )


def test_all_new_pass_through(db_path):
    jobs = [_job("A", "E1"), _job("B", "E2")]
    result = dedup_jobs(jobs, db_path=db_path)
    assert len(result) == 2


def test_existing_dedup_key_filtered(db_path, con):
    con.execute(
        "INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://old.com', 't', 'Acme::SWE')"
    )
    con.commit()
    con.close()
    jobs = [_job("Acme", "SWE", "http://new.com")]
    result = dedup_jobs(jobs, db_path=db_path)
    assert result == []


def test_mixed_new_and_existing(db_path, con):
    con.execute(
        "INSERT INTO jobs (url, provider, dedup_key) VALUES ('http://x.com', 't', 'Acme::SWE')"
    )
    con.commit()
    con.close()
    jobs = [_job("Acme", "SWE"), _job("Beta", "Dev", "http://y.com")]
    result = dedup_jobs(jobs, db_path=db_path)
    assert len(result) == 1
    assert result[0].company == "Beta"


def test_empty_input(db_path):
    assert dedup_jobs([], db_path=db_path) == []
