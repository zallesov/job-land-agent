from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
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
        page.bring_to_front()
        try:
            ok = wait_for_auth(page, "jobleads", CHECK_URL, _is_auth_page)
        finally:
            page.close()
    if not ok:
        raise AuthError("JobLeads auth timed out")


if __name__ == "__main__":
    check_auth(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9222")
