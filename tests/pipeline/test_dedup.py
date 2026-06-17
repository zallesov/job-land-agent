from scripts.pipeline.types import ShallowJob
from scripts.pipeline.dedup import dedup_jobs


def _job(company="Acme", title="SWE", url="http://x.com"):
    return ShallowJob(
        provider="test", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date=None, salary_raw=None,
    )


def test_all_new_pass_through(pb):
    jobs = [_job("A", "E1"), _job("B", "E2")]
    result = dedup_jobs(jobs)
    assert len(result) == 2


def test_existing_dedup_key_filtered(pb):
    pb.create("jobs", {"url": "http://old.com", "provider": "t", "dedup_key": "Acme::SWE"})
    jobs = [_job("Acme", "SWE", "http://new.com")]
    result = dedup_jobs(jobs)
    assert result == []


def test_mixed_new_and_existing(pb):
    pb.create("jobs", {"url": "http://x.com", "provider": "t", "dedup_key": "Acme::SWE"})
    jobs = [_job("Acme", "SWE"), _job("Beta", "Dev", "http://y.com")]
    result = dedup_jobs(jobs)
    assert len(result) == 1
    assert result[0].company == "Beta"


def test_empty_input(pb):
    assert dedup_jobs([]) == []
