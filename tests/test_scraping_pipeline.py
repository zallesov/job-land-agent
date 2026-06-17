from unittest.mock import patch, MagicMock
from scripts.pipeline.types import ShallowJob, HermesResult

BERLIN = {"city": "Berlin", "country": "Germany", "country_code": "DE"}
CDP = "http://localhost:9222"


def _job(company="Acme", title="SWE", url="http://x.com"):
    return ShallowJob(
        provider="greenhouse", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date=None, salary_raw=None,
    )


def test_happy_path(pb):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[_job()])
    jid = "fake000000000001"

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[_job()]) as mock_dedup, \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[jid]) as mock_ingest, \
         patch("scripts.scraping_pipeline.enrich_job") as mock_enrich, \
         patch("scripts.scraping_pipeline.screen_job") as mock_screen, \
         patch("scripts.scraping_pipeline.send_daily_digest") as mock_notify:

        mock_enrich.return_value = HermesResult(
            success=True, data={"status": "success"}, error=None, raw_output=""
        )
        mock_screen.return_value = HermesResult(
            success=True, data={"status": "success", "verdict": "pass"},
            error=None, raw_output=""
        )

        from scripts.scraping_pipeline import run
        run(provider="greenhouse", cdp_url=CDP,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape)

    mock_check_auth.assert_called_once_with(CDP)
    mock_scrape.assert_called_once_with(CDP, titles=None)
    mock_dedup.assert_called_once()
    mock_ingest.assert_called_once()
    mock_enrich.assert_called_once_with(jid)
    mock_screen.assert_called_once_with(jid)
    mock_notify.assert_called_once_with(enrich_failures=[], screen_failures=[])


def test_auth_error_stops_pipeline(pb):
    from scripts.providers.greenhouse.check_auth import AuthError
    mock_check_auth = MagicMock(side_effect=AuthError("timed out"))
    mock_scrape = MagicMock()

    import pytest
    from scripts.scraping_pipeline import run
    with pytest.raises(AuthError):
        run(provider="greenhouse", cdp_url=CDP,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape)
    mock_scrape.assert_not_called()


def test_enrich_failure_skips_screen_for_that_job(pb):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[_job()])
    jid = "fake000000000002"

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[_job()]), \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[jid]), \
         patch("scripts.scraping_pipeline.enrich_job") as mock_enrich, \
         patch("scripts.scraping_pipeline.screen_job") as mock_screen, \
         patch("scripts.scraping_pipeline.send_daily_digest") as mock_notify:

        mock_enrich.return_value = HermesResult(
            success=False, data={}, error="timeout", raw_output=""
        )

        from scripts.scraping_pipeline import run
        run(provider="greenhouse", cdp_url=CDP,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape)

    mock_screen.assert_not_called()
    failures = mock_notify.call_args[1]["enrich_failures"]
    assert (jid, "timeout") in failures


def test_titles_passed_to_scrape_jobs(pb):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[])

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[]), \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[]), \
         patch("scripts.scraping_pipeline.send_daily_digest"):
        from scripts.scraping_pipeline import run
        run(
            provider="greenhouse",
            titles=["AI Engineer", "Software Engineer"],
            cdp_url=CDP,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )

    mock_scrape.assert_called_once_with(
        CDP, titles=["AI Engineer", "Software Engineer"]
    )


def test_hirify_is_registered_provider():
    from scripts.scraping_pipeline import PROVIDERS

    assert "hirify" in PROVIDERS
