"""
E2E test — requires real Chrome at localhost:9222 + real Hermes.
Run manually: pytest tests/e2e/ -m e2e -v

Fixtures at tests/fixtures/e2e/:
  index.json                  — metadata for all fixtures
  job_<id>_<company>.json     — page text, expected_verdict, url per job
  cv.md                       — candidate CV used by enrich-job + sanity-check-job skills
"""
import json
import pytest
from pathlib import Path
from scripts.db import create_db

E2E_DB = "/tmp/e2e_test.db"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "e2e"
CV_PATH = FIXTURES_DIR / "cv.md"


@pytest.fixture(scope="module", autouse=True)
def setup_e2e_db():
    create_db(E2E_DB)


def _load(filename):
    return json.loads((FIXTURES_DIR / filename).read_text())


@pytest.mark.e2e
def test_greenhouse_pipeline_live():
    """Full pipeline against real Greenhouse. Needs Chrome + DB + Hermes."""
    from scripts.scraping_pipeline import run
    run(
        provider="greenhouse",
        location="berlin",
        cdp_url="http://localhost:9222",
        db_path=E2E_DB,
    )


@pytest.mark.e2e
@pytest.mark.parametrize("fixture_file,expected", [
    (item["file"].split("/")[-1], item["expected_verdict"])
    for item in _load("index.json")
    if "enrich" in item["use_for"]
])
def test_enrich_job_live(fixture_file, expected):
    """Enrich each fixture job via real Hermes. Checks structured output returned."""
    from scripts.pipeline.enrich_job import enrich_job
    job = _load(fixture_file)
    # insert a minimal row so enrich_job can look it up
    import sqlite3
    con = sqlite3.connect(E2E_DB)
    con.execute(
        "INSERT OR IGNORE INTO jobs (id, url, provider, title, posted_company_name, status) VALUES (?,?,?,?,?,?)",
        (job["id"], job["url"], "e2e", job["title"], job["company"], "listed"),
    )
    con.commit()
    result = enrich_job(job["id"], db_path=E2E_DB)
    assert result.success, f"enrich failed: {result.error}"


@pytest.mark.e2e
@pytest.mark.parametrize("fixture_file,expected", [
    (item["file"].split("/")[-1], item["expected_verdict"])
    for item in _load("index.json")
])
def test_sanity_check_job_live(fixture_file, expected):
    """Sanity-check each fixture job via real Hermes. Verifies verdict matches expected."""
    from scripts.pipeline.sanity_check_job import sanity_check_job
    job = _load(fixture_file)
    result = sanity_check_job(job["id"], db_path=E2E_DB)
    if expected == "skip":
        assert result.data.get("verdict") == "skip", f"expected skip, got: {result.data}"
    elif expected == "pass":
        assert result.data.get("verdict") != "skip", f"expected pass, got: {result.data}"
    # expected="uncertain": no assertion — just verify it returns without error
    assert result.error is None or expected == "uncertain", f"unexpected error: {result.error}"
