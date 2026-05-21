from __future__ import annotations
import re
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://www.jobleads.com/search/jobs"


def is_auth_page(url: str) -> bool:
    return bool(re.search(r"/external-home|accounts\.google\.com|modal=login|sign.in", url))


def check_auth(page, timeout_sec: int = 600) -> bool:
    return wait_for_auth(page, "jobleads", CHECK_URL, is_auth_page, timeout_sec=timeout_sec)
