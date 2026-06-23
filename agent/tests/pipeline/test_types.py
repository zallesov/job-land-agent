from scripts.pipeline.types import ShallowJob, HermesResult


def test_shallow_job_dedup_key():
    j = ShallowJob(
        provider="gh", title="SWE", company="Acme", url="http://x", location="Remote",
        country="DE", dedup_key="Acme::SWE", posting_date=None, salary_raw=None,
    )
    assert j.dedup_key == "Acme::SWE"


def test_hermes_result_fields():
    r = HermesResult(success=True, data={"status": "success"}, error=None, raw_output="{}")
    assert r.success is True
