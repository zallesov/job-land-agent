from __future__ import annotations
import re
from playwright.sync_api import sync_playwright
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://wellfound.com/jobs"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"/login|/signin|sign_in|/auth", url, re.I))


def check_auth(cdp_url: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "wellfound", CHECK_URL, _is_auth_page)
        finally:
            page.close()
    if not ok:
        raise AuthError("Wellfound auth timed out")
