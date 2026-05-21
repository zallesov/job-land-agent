import json
from pathlib import Path
from unittest.mock import MagicMock, patch

BERLIN = {"city": "Berlin", "country": "Germany", "country_code": "DE"}

FIXTURE = Path(__file__).parent.parent.parent / "fixtures" / "jobleads" / "scrape_output.json"

# Fixture has 2 jobs:
#   - Remote company / Senior Data Platform Engineer (relevant)
#   - Fintech startup / Head of Engineering (relevant)
# Both pass is_relevant(), so we expect 2 results.


@patch("scripts.providers.jobleads.scrape_jobs.collect_jobleads")
@patch("scripts.providers.jobleads.scrape_jobs.sync_playwright")
def test_returns_shallow_jobs(mock_pw, mock_collect):
    raw = json.loads(FIXTURE.read_text())
    mock_collect.return_value = raw
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.jobleads.scrape_jobs import scrape_jobs
    jobs = scrape_jobs(BERLIN, "http://localhost:9222")
    assert len(jobs) == 2
    assert all(j.provider == "jobleads" for j in jobs)
    assert all("::" in j.dedup_key for j in jobs)
    titles = {j.title for j in jobs}
    assert "Senior Data Platform Engineer" in titles
    assert "Head of Engineering" in titles


@patch("scripts.providers.jobleads.scrape_jobs.collect_jobleads")
@patch("scripts.providers.jobleads.scrape_jobs.sync_playwright")
def test_irrelevant_jobs_filtered(mock_pw, mock_collect):
    mock_collect.return_value = [
        {"provider": "jobleads", "company": "Corp", "title": "Sales Manager DACH",
         "url": "http://x.com", "location": "Remote", "country": "DE",
         "postedRelative": "", "salaryRaw": ""}
    ]
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.jobleads.scrape_jobs import scrape_jobs
    jobs = scrape_jobs(BERLIN, "http://localhost:9222")
    assert len(jobs) == 1 and jobs[0].status == "skip"
