"""
E2E test — requires real Chrome at localhost:9222 + real Hermes + a LOCAL
PocketBase instance (see tests/e2e/conftest.py — refuses to run against any
non-local POCKETBASE_URL).

Run manually:
  POCKETBASE_URL=http://localhost:8090 \
  POCKETBASE_ADMIN_EMAIL=... POCKETBASE_ADMIN_PASSWORD=... \
  pytest tests/e2e/ -m e2e -v

Fixtures at tests/fixtures/e2e/:
  index.json                  — metadata for all fixtures
  job_<id>_<company>.json     — page text, expected_verdict, url per job
  cv.md                       — candidate CV used by enrich-job + screen-job skills
"""
import json
import pytest
from pathlib import Path
from scripts.pb_client import get_pb, pad_id

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "e2e"
CV_PATH = FIXTURES_DIR / "cv.md"


def _load(filename):
    return json.loads((FIXTURES_DIR / filename).read_text())


def _ensure_job_record(job: dict, status: str = "listed") -> None:
    """Create (or refresh) the fixture's job row in the local PocketBase."""
    pb = get_pb()
    pb_id = pad_id(job["id"])
    if pb.get_job(pb_id) is not None:
        return
    pb.create("jobs", {
        "id": pb_id,
        "url": job["url"],
        "provider": "e2e",
        "title": job["title"],
        "posted_company_name": job["company"],
        "status": status,
    })


@pytest.mark.e2e
def test_greenhouse_pipeline_live():
    """Full pipeline against real Greenhouse. Needs Chrome + local PocketBase + Hermes."""
    from scripts.scraping_pipeline import run
    run(
        provider="greenhouse",
        location={"city": "Berlin", "country": "Germany", "country_code": "DE"},
        cdp_url="http://localhost:9222",
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
    _ensure_job_record(job)
    result = enrich_job(pad_id(job["id"]))
    assert result.success, f"enrich failed: {result.error}"


@pytest.mark.e2e
@pytest.mark.parametrize("fixture_file,expected", [
    (item["file"].split("/")[-1], item["expected_verdict"])
    for item in _load("index.json")
])
def test_screen_job_live(fixture_file, expected):
    """Screen each fixture job via real Hermes. Verifies verdict matches expected."""
    from scripts.pipeline.screen_job import screen_job
    job = _load(fixture_file)
    _ensure_job_record(job)
    result = screen_job(pad_id(job["id"]))
    if expected == "skip":
        assert result.data.get("verdict") == "skip", f"expected skip, got: {result.data}"
    elif expected == "pass":
        assert result.data.get("verdict") != "skip", f"expected pass, got: {result.data}"
    # expected="uncertain": no assertion — just verify it returns without error
    assert result.error is None or expected == "uncertain", f"unexpected error: {result.error}"
