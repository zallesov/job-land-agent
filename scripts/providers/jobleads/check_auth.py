from __future__ import annotations
import re
from playwright.sync_api import sync_playwright
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://www.jobleads.com/search/jobs"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"/external-home|accounts\.google\.com|modal=login|sign.in", url))


def check_auth(cdp_url: str) -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            ok = wait_for_auth(page, "jobleads", CHECK_URL, _is_auth_page)
        finally:
            browser.close()
    if not ok:
        raise AuthError("JobLeads auth timed out")
