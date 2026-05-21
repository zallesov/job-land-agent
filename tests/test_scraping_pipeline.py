from unittest.mock import patch, MagicMock
from scripts.pipeline.types import ShallowJob, HermesResult

BERLIN = {"city": "Berlin", "country": "Germany", "country_code": "DE"}


def _job(company="Acme", title="SWE", url="http://x.com"):
    return ShallowJob(
        provider="greenhouse", title=title, company=company, url=url,
        location="Remote", country="DE",
        dedup_key=f"{company}::{title}",
        posting_date=None, salary_raw=None,
    )


def test_happy_path(db_path):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[_job()])
    jid = 1

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[_job()]) as mock_dedup, \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[jid]) as mock_ingest, \
         patch("scripts.scraping_pipeline.enrich_job") as mock_enrich, \
         patch("scripts.scraping_pipeline.sanity_check_job") as mock_sanity, \
         patch("scripts.scraping_pipeline.send_daily_digest") as mock_notify:

        mock_enrich.return_value = HermesResult(
            success=True, data={"status": "success"}, error=None, raw_output=""
        )
        mock_sanity.return_value = HermesResult(
            success=True, data={"status": "success", "verdict": "pass"},
            error=None, raw_output=""
        )

        from scripts.scraping_pipeline import run
        run(
            provider="greenhouse", location=BERLIN,
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )

    mock_check_auth.assert_called_once_with("http://localhost:9222")
    mock_scrape.assert_called_once_with(BERLIN, "http://localhost:9222", titles=None, db_path=db_path)
    mock_dedup.assert_called_once()
    mock_ingest.assert_called_once()
    mock_enrich.assert_called_once_with(jid, db_path=db_path)
    mock_sanity.assert_called_once_with(jid, db_path=db_path)
    mock_notify.assert_called_once_with(enrich_failures=[], sanity_failures=[])


def test_auth_error_stops_pipeline(db_path):
    from scripts.providers.greenhouse.check_auth import AuthError
    mock_check_auth = MagicMock(side_effect=AuthError("timed out"))
    mock_scrape = MagicMock()

    import pytest
    from scripts.scraping_pipeline import run
    with pytest.raises(AuthError):
        run(
            provider="greenhouse", location=BERLIN,
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )
    mock_scrape.assert_not_called()


def test_enrich_failure_skips_sanity_for_that_job(db_path):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[_job()])
    jid = 2

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[_job()]), \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[jid]), \
         patch("scripts.scraping_pipeline.enrich_job") as mock_enrich, \
         patch("scripts.scraping_pipeline.sanity_check_job") as mock_sanity, \
         patch("scripts.scraping_pipeline.send_daily_digest") as mock_notify:

        mock_enrich.return_value = HermesResult(
            success=False, data={}, error="timeout", raw_output=""
        )

        from scripts.scraping_pipeline import run
        run(
            provider="greenhouse", location=BERLIN,
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )

    mock_sanity.assert_not_called()
    failures = mock_notify.call_args[1]["enrich_failures"]
    assert (jid, "timeout") in failures


def test_titles_passed_to_scrape_jobs(db_path):
    mock_check_auth = MagicMock()
    mock_scrape = MagicMock(return_value=[])

    with patch("scripts.scraping_pipeline.dedup_jobs", return_value=[]), \
         patch("scripts.scraping_pipeline.ingest_jobs", return_value=[]), \
         patch("scripts.scraping_pipeline.send_daily_digest"):
        from scripts.scraping_pipeline import run
        run(
            provider="greenhouse", location=BERLIN,
            titles=["AI Engineer", "Software Engineer"],
            cdp_url="http://localhost:9222", db_path=db_path,
            _check_auth=mock_check_auth, _scrape_jobs=mock_scrape,
        )

    mock_scrape.assert_called_once_with(
        BERLIN, "http://localhost:9222", titles=["AI Engineer", "Software Engineer"], db_path=db_path
    )
