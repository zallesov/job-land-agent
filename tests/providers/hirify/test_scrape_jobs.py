from scripts.providers.hirify.scrape_jobs import (
    HIRIFY_BASE,
    _canonical_url,
    _normalize_raw_job,
)
from unittest.mock import MagicMock


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
