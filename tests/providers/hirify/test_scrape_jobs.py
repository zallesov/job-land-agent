from scripts.providers.hirify.scrape_jobs import (
    HIRIFY_BASE,
    _canonical_url,
    _normalize_raw_job,
)
from unittest.mock import MagicMock, patch


def test_canonical_url_resolves_relative_hirify_links():
    assert _canonical_url("/jobs/123-ai-engineer") == "https://hirify.me/jobs/123-ai-engineer"


def test_normalize_raw_job_maps_required_fields():
    raw = {
        "title": "Senior AI Engineer",
        "company": "Acme",
        "url": "/jobs/123-ai-engineer?utm_source=x",
        "location": "remote Germany fulltime senior",
        "country": "Germany",
        "salaryRaw": "100 000 - 130 000 EUR",
    }

    job = _normalize_raw_job(raw)

    assert job.provider == "hirify"
    assert job.title == "Senior AI Engineer"
    assert job.company == "Acme"
    assert job.url == f"{HIRIFY_BASE}/jobs/123-ai-engineer"
    assert job.location == "remote Germany fulltime senior"
    assert job.country == "Germany"
    assert job.dedup_key == "Acme::Senior AI Engineer"
    assert job.salary_raw == "100 000 - 130 000 EUR"
    assert job.posting_date is None
    assert job.status == "listed"


def test_normalize_raw_job_uses_company_hidden_fallback():
    job = _normalize_raw_job({
        "title": "Backend Engineer",
        "company": "",
        "url": "https://hirify.me/jobs/456-backend",
    })

    assert job.company == "Company hidden"
    assert job.dedup_key == "Company hidden::Backend Engineer"


def test_get_saved_filters_extracts_labels_and_indexes():
    from scripts.providers.hirify import scrape_jobs as mod

    page = MagicMock()
    page.evaluate.return_value = [
        {"index": 0, "label": "AI Remote"},
        {"index": 1, "label": "Backend Europe"},
    ]

    filters = mod._get_saved_filters(page)

    assert filters == [
        {"index": 0, "label": "AI Remote"},
        {"index": 1, "label": "Backend Europe"},
    ]
    assert "saved" in page.evaluate.call_args[0][0].lower()


def test_collect_current_page_jobs_returns_raw_rows():
    from scripts.providers.hirify import scrape_jobs as mod

    page = MagicMock()
    page.evaluate.return_value = [{
        "title": "AI Engineer",
        "company": "Acme",
        "url": "https://hirify.me/jobs/1",
        "location": "remote Germany",
        "country": "Germany",
        "salaryRaw": "100 000 EUR",
    }]

    rows = mod._collect_current_page_jobs(page)

    assert rows[0]["title"] == "AI Engineer"
    assert rows[0]["url"] == "https://hirify.me/jobs/1"


def test_scrape_filter_pages_stops_when_next_disappears():
    from scripts.providers.hirify import scrape_jobs as mod

    page = MagicMock()
    with patch.object(mod, "_collect_current_page_jobs", side_effect=[
        [{"title": "AI Engineer", "company": "Acme", "url": "https://hirify.me/jobs/1"}],
        [{"title": "Backend Engineer", "company": "Beta", "url": "https://hirify.me/jobs/2"}],
    ]), patch.object(mod, "_click_next_page", side_effect=[True, False]):
        rows = mod._scrape_filter_pages(page)

    assert [r["url"] for r in rows] == ["https://hirify.me/jobs/1", "https://hirify.me/jobs/2"]


def test_scrape_jobs_dedups_across_filters_and_ignores_titles():
    from scripts.providers.hirify import scrape_jobs as mod

    pw_mock = MagicMock()
    page = MagicMock()
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    pw_instance = MagicMock()
    pw_instance.chromium.connect_over_cdp.return_value = browser
    pw_mock.__enter__.return_value = pw_instance
    pw_mock.__exit__.return_value = False

    raw = [
        {"title": "Backend Engineer", "company": "Acme", "url": "https://hirify.me/jobs/1"},
        {"title": "Backend Engineer", "company": "Acme", "url": "https://hirify.me/jobs/1"},
    ]

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "_get_saved_filters", return_value=[{"index": 0, "label": "A"}, {"index": 1, "label": "B"}]), \
         patch.object(mod, "_activate_saved_filter"), \
         patch.object(mod, "_scrape_filter_pages", return_value=raw), \
         patch.object(mod, "is_relevant", return_value=True):
        jobs = mod.scrape_jobs("http://localhost:9222", titles=["AI Engineer"])

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    page.goto.assert_called_once_with(mod.HIRIFY_BASE, wait_until="domcontentloaded", timeout=30000)
