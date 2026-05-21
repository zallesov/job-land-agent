import json
from pathlib import Path
from unittest.mock import MagicMock, patch

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "sprout" / "scrape_output.json"

# Fixture has 1 job:
#   - Bluefish AI / Staff AI Platform Engineer (relevant)


@patch("scripts.providers.sprout.scrape_jobs.collect_sprout")
@patch("scripts.providers.sprout.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_collect):
    raw = json.loads(FIXTURE.read_text())
    mock_collect.return_value = raw
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.sprout.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert len(jobs) == 1
    assert jobs[0].provider == "sprout"
    assert jobs[0].title == "Staff AI Platform Engineer"
    assert jobs[0].company == "Bluefish AI"
    assert "::" in jobs[0].dedup_key


@patch("scripts.providers.sprout.scrape_jobs.collect_sprout")
@patch("scripts.providers.sprout.scrape_jobs.sync_playwright")
def test_irrelevant_jobs_filtered(mock_pw, mock_collect):
    mock_collect.return_value = [
        {"provider": "sprout", "company": "Corp", "title": "Account Executive",
         "url": "http://x.com", "location": "Remote", "country": "Germany",
         "date": "", "salary": ""}
    ]
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.sprout.scrape_jobs import scrape_jobs
    jobs = scrape_jobs("berlin", "http://localhost:9222")
    assert jobs == []
