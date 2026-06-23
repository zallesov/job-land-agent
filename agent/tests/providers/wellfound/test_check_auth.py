from unittest.mock import MagicMock, patch
import pytest


@patch("scripts.providers.wellfound.check_auth.sync_playwright")
def test_already_authenticated(mock_pw):
    page = MagicMock()
    page.url = "https://wellfound.com/jobs"
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser

    from scripts.providers.wellfound.check_auth import check_auth
    check_auth("http://localhost:9222")  # should not raise


@patch("scripts.providers.wellfound.check_auth.sync_playwright")
@patch("scripts.providers.wellfound.check_auth.wait_for_auth")
def test_auth_required_raises_on_timeout(mock_wait, mock_pw):
    page = MagicMock()
    page.url = "https://wellfound.com/login"
    ctx = MagicMock()
    ctx.new_page.return_value = page
    browser = MagicMock()
    browser.contexts = [ctx]
    mock_pw.return_value.__enter__.return_value.chromium.connect_over_cdp.return_value = browser
    mock_wait.return_value = False  # timeout

    from scripts.providers.wellfound.check_auth import check_auth, AuthError
    with pytest.raises(AuthError):
        check_auth("http://localhost:9222")
