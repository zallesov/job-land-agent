import json
from pathlib import Path
from unittest.mock import MagicMock, patch

BERLIN = {"city": "Berlin", "country": "Germany", "country_code": "DE"}

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "greenhouse" / "scrape_output.json"

# Fixture has 4 jobs:
#   - Clarity AI / Staff AI Engineer (relevant)
#   - Zencoder / Staff Software Engineer (relevant)
#   - Bluefish AI / Engineering Manager (Data Team) (relevant)
#   - Acme Corp (Sales) / Sales Manager DACH (irrelevant — filtered)


@patch("scripts.providers.greenhouse.scrape_jobs.collect_greenhouse")
@patch("scripts.providers.greenhouse.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_collect):
    raw = json.loads(FIXTURE.read_text())
    mock_collect.return_value = raw
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.greenhouse.scrape_jobs import scrape_jobs
    jobs = scrape_jobs(BERLIN, "http://localhost:9222")
    # 3 relevant jobs pass through; Sales Manager DACH is filtered
    assert len(jobs) == 3
    assert all(j.provider == "greenhouse" for j in jobs)
    assert all("::" in j.dedup_key for j in jobs)
    titles = {j.title for j in jobs}
    assert "Staff AI Engineer" in titles
    assert "Staff Software Engineer" in titles
    assert "Engineering Manager (Data Team)" in titles
    assert "Sales Manager DACH" not in titles


@patch("scripts.providers.greenhouse.scrape_jobs.collect_greenhouse")
@patch("scripts.providers.greenhouse.scrape_jobs.sync_playwright")
def test_irrelevant_jobs_filtered(mock_pw, mock_collect):
    mock_collect.return_value = [
        {"provider": "greenhouse", "company": "X", "title": "Sales Manager DACH",
         "url": "http://x.com", "location": "Remote", "country": "DE",
         "postingDate": "", "applyUrl": "", "salaryRaw": ""}
    ]
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.greenhouse.scrape_jobs import scrape_jobs
    jobs = scrape_jobs(BERLIN, "http://localhost:9222")
    assert jobs == []


@patch("scripts.providers.greenhouse.scrape_jobs.collect_greenhouse")
@patch("scripts.providers.greenhouse.scrape_jobs.sync_playwright")
def test_missing_title_or_company_skipped(mock_pw, mock_collect):
    mock_collect.return_value = [
        {"provider": "greenhouse", "company": "", "title": "Software Engineer",
         "url": "http://x.com", "location": "Remote", "country": "DE",
         "postingDate": "", "applyUrl": "", "salaryRaw": ""},
        {"provider": "greenhouse", "company": "ACME", "title": "",
         "url": "http://x.com", "location": "Remote", "country": "DE",
         "postingDate": "", "applyUrl": "", "salaryRaw": ""},
    ]
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.greenhouse.scrape_jobs import scrape_jobs
    jobs = scrape_jobs(BERLIN, "http://localhost:9222")
    assert jobs == []
