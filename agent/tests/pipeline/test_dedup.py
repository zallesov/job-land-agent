from scripts.pipeline.types import ShallowJob
from scripts.pipeline.dedup import dedup_jobs


def _job(company="Acme", title="SWE", url="http://x.com"):
    return ShallowJob(
        provider="test", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date=None, salary_raw=None,
    )


def _existing(company="Acme", title="SWE", url="http://old.com"):
    return {"url": url, "provider": "t", "dedup_key": f"{company}::{title}"}


def test_all_new_pass_through():
    jobs = [_job("A", "E1"), _job("B", "E2")]
    result = dedup_jobs(jobs, [])
    assert len(result) == 2


def test_existing_dedup_key_filtered():
    existing = [_existing("Acme", "SWE")]
    jobs = [_job("Acme", "SWE", "http://new.com")]
    assert dedup_jobs(jobs, existing) == []


def test_mixed_new_and_existing():
    existing = [_existing("Acme", "SWE", "http://x.com")]
    jobs = [_job("Acme", "SWE"), _job("Beta", "Dev", "http://y.com")]
    result = dedup_jobs(jobs, existing)
    assert len(result) == 1
    assert result[0].company == "Beta"


def test_within_batch_dedup():
    jobs = [_job("Acme", "SWE"), _job("Acme", "SWE", "http://dup.com")]
    result = dedup_jobs(jobs, [])
    assert len(result) == 1


def test_existing_none_is_treated_as_empty():
    assert len(dedup_jobs([_job("A", "E1")], None)) == 1


def test_empty_input():
    assert dedup_jobs([], []) == []
