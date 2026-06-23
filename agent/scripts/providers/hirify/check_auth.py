from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from playwright.sync_api import sync_playwright

from scripts.providers.hirify.cdp_fallback import CdpPage
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://hirify.me/"


class AuthError(Exception):
    pass


def _is_auth_page(url: str) -> bool:
    return bool(re.search(r"modal=login|sign.?in|accounts\.google\.com", url, re.I))


def _has_authenticated_controls(page) -> bool:
    try:
        text = (page.locator("body").inner_text(timeout=5000) or "").lower()
    except Exception:
        return False
    # Accept if page has job-browsing content without a hard login gate
    has_jobs_content = "sign in" not in text or "saved" in text or "jobs" in text
    hard_login_gate = re.search(r"(^|\s)(sign in|log in)(\s|$)", text) and "saved" not in text and "jobs" not in text
    return has_jobs_content and not hard_login_gate


def check_auth(cdp_url: str) -> None:
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]
            page = ctx.new_page()
            page.bring_to_front()
            try:
                ok = wait_for_auth(page, "hirify", CHECK_URL, _is_auth_page)
                if ok and not _has_authenticated_controls(page):
                    ok = False
            finally:
                page.close()
    except Exception as e:
        if "Browser.setDownloadBehavior" not in str(e):
            raise
        page = CdpPage(cdp_url)
        try:
            page.goto(CHECK_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            ok = not _is_auth_page(page.url) and _has_authenticated_controls(page)
        finally:
            page.close()
    if not ok:
        raise AuthError("Hirify auth timed out")


if __name__ == "__main__":
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
