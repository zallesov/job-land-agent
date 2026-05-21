from __future__ import annotations
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://wellfound.com/jobs"


def is_auth_page(url: str) -> bool:
    return any(kw in url.lower() for kw in ("sign_in", "login", "/auth"))


def check_auth(page, timeout_sec: int = 600) -> bool:
    return wait_for_auth(page, "wellfound", CHECK_URL, is_auth_page, timeout_sec=timeout_sec)
