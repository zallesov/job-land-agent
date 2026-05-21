from __future__ import annotations
from scripts.providers._shared.auth_check import wait_for_auth

CHECK_URL = "https://app.usesprout.com/jobs?view=board"


def is_auth_page(url: str) -> bool:
    return "sign-in" in url or "/auth" in url


def check_auth(page, timeout_sec: int = 600) -> bool:
    return wait_for_auth(page, "sprout", CHECK_URL, is_auth_page, timeout_sec=timeout_sec)
