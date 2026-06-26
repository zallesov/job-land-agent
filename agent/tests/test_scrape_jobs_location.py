"""Tests for provider scrape_jobs location dict interface."""
from unittest.mock import MagicMock, patch

BERLIN = {"city": "Berlin", "country": "Germany", "country_code": "DE"}
BARCELONA = {"city": "Barcelona", "country": "Spain", "country_code": "ES"}


def _make_playwright_mock(collect_return_value: list[dict]):
    """Return (pw_context_manager, mock_page) ready to use in patches."""
    mock_page = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.new_page.return_value = mock_page
    mock_browser = MagicMock()
    mock_browser.contexts = [mock_ctx]
    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.connect_over_cdp.return_value = mock_browser
    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)
    return mock_pw_cm


def test_greenhouse_accepts_location_dict_and_country_code():
    """greenhouse scrape_jobs uses country_code in URL, not LOCATION_PRESETS."""
    from scripts.providers.greenhouse import scrape_jobs as mod

    raw = [{"title": "AI Engineer", "company": "Acme", "url": "http://x.com",
            "location": "Remote", "country": "DE"}]
    pw_mock = _make_playwright_mock(raw)

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_greenhouse", return_value=raw) as mock_collect, \
         patch.object(mod, "is_relevant", return_value=True):
        result = mod.scrape_jobs(BERLIN, "http://localhost:9222")

    # URL must use country_short_name=DE (country-level, not city-level lat/lon)
    search_arg = mock_collect.call_args[0][1]
    assert "country_short_name=DE" in search_arg["url"]
    assert "location_type=country" in search_arg["url"]
    assert len(result) == 1


def test_greenhouse_title_filter():
    """greenhouse scrape_jobs filters by titles when provided."""
    from scripts.providers.greenhouse import scrape_jobs as mod

    raw = [
        {"title": "Software Engineer", "company": "Acme", "url": "http://a.com",
         "location": "Remote", "country": "DE"},
        {"title": "AI Engineer", "company": "Acme", "url": "http://b.com",
         "location": "Remote", "country": "DE"},
    ]
    pw_mock = _make_playwright_mock(raw)

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_greenhouse", return_value=raw), \
         patch.object(mod, "is_relevant", return_value=True):
        result = mod.scrape_jobs(BERLIN, "http://localhost:9222", titles=["AI Engineer"])

    assert len(result) == 1
    assert result[0].title == "AI Engineer"


def test_jobleads_accepts_location_dict():
    """jobleads scrape_jobs passes city/country through to collect_jobleads.

    JobLeads has no URL-param location filter — _run_search drives the site's
    country dropdown + location input directly, so the search dict carries
    city/country fields rather than a pre-built URL.
    """
    from scripts.providers.jobleads import scrape_jobs as mod

    raw = [{"title": "Platform Engineer", "company": "Corp", "url": "http://c.com",
            "location": "Remote", "country": "ES"}]
    pw_mock = _make_playwright_mock(raw)

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_jobleads", return_value=raw) as mock_collect, \
         patch.object(mod, "is_relevant", return_value=True):
        result = mod.scrape_jobs(BARCELONA, "http://localhost:9222")

    search_arg = mock_collect.call_args[0][1]
    assert search_arg["city"] == "Barcelona"
    assert search_arg["country"] == "Spain"
    assert len(result) == 1


def test_sprout_passes_titles_to_collect():
    """sprout scrape_jobs passes titles to collect_sprout."""
    from scripts.providers.sprout import scrape_jobs as mod

    pw_mock = _make_playwright_mock([])

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_sprout", return_value=[]) as mock_collect:
        mod.scrape_jobs(BERLIN, "http://localhost:9222", titles=["AI Engineer"])

    collect_kwargs = mock_collect.call_args[1]
    assert collect_kwargs["titles"] == ["AI Engineer"]
    assert collect_kwargs["location"] == "Berlin"


def test_sprout_uses_default_titles_when_none():
    """sprout falls back to DEFAULT_TITLES when titles=None."""
    from scripts.providers.sprout import scrape_jobs as mod
    from scripts.providers.sprout.scrape_jobs import DEFAULT_TITLES

    pw_mock = _make_playwright_mock([])

    with patch.object(mod, "sync_playwright", return_value=pw_mock), \
         patch.object(mod, "collect_sprout", return_value=[]) as mock_collect:
        mod.scrape_jobs(BERLIN, "http://localhost:9222")

    collect_kwargs = mock_collect.call_args[1]
    assert collect_kwargs["titles"] == DEFAULT_TITLES
