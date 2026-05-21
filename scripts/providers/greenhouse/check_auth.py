from __future__ import annotations
from playwright.sync_api import sync_playwright
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://my.greenhouse.io/jobs"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return "/users/sign_in" in url


def check_auth(cdp_url: str) -> None:
    """Raises AuthError if Greenhouse session cannot be established."""
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "greenhouse", CHECK_URL, _is_auth_page)
        finally:
            page.close()
    if not ok:
        raise AuthError("Greenhouse auth timed out")
