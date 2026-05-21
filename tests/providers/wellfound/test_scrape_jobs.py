import json
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "wellfound" / "scrape_output.json"

# Fixture has 1 job:
#   - Zencoder / Staff Software Engineer (relevant)


@patch("scripts.providers.wellfound.scrape_jobs.collect_wellfound")
@patch("scripts.providers.wellfound.scrape_jobs.apply_filters")
@patch("scripts.providers.wellfound.scrape_jobs.change_location")
@patch("scripts.providers.wellfound.scrape_jobs.scroll_to_load_all")
@patch("scripts.providers.wellfound.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_scroll, mock_loc, mock_filters, mock_collect):
    raw = json.loads(FIXTURE.read_text())
    mock_collect.return_value = raw
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.wellfound.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert len(jobs) == 1
    assert jobs[0].provider == "wellfound"
    assert jobs[0].title == "Staff Software Engineer"
    assert jobs[0].company == "Zencoder"
    assert "::" in jobs[0].dedup_key


@patch("scripts.providers.wellfound.scrape_jobs.collect_wellfound")
@patch("scripts.providers.wellfound.scrape_jobs.apply_filters")
@patch("scripts.providers.wellfound.scrape_jobs.change_location")
@patch("scripts.providers.wellfound.scrape_jobs.scroll_to_load_all")
@patch("scripts.providers.wellfound.scrape_jobs.sync_playwright")
def test_irrelevant_jobs_filtered(mock_pw, mock_scroll, mock_loc, mock_filters, mock_collect):
    mock_collect.return_value = [
        {"provider": "wellfound", "company": "Corp", "title": "Head of Sales",
         "url": "http://x.com", "location": "Remote", "country": "Germany",
         "postingDate": "", "salaryRaw": "", "equityRaw": ""}
    ]
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.wellfound.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert jobs == []
