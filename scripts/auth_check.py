#!/usr/bin/env python3
"""
Shared auth preflight for all scrapers.

Usage in each scraper's main():
    from scripts.auth_check import wait_for_auth
    if not wait_for_auth(page, "greenhouse", "https://my.greenhouse.io/jobs", is_auth_page):
        raise SystemExit(10)
"""
from __future__ import annotations

import subprocess
import sys
import time
from typing import Callable

HERMES = "hermes"
TELEGRAM_TARGET = "telegram"


def _notify(msg: str) -> None:
    subprocess.run(
        [HERMES, "send", "--to", TELEGRAM_TARGET, msg],
        capture_output=True,
    )


def wait_for_auth(
    page,
    provider: str,
    check_url: str,
    is_auth_page_fn: Callable[[str], bool],
    timeout_sec: int = 600,
    poll_sec: int = 15,
) -> bool:
    """
    Navigate to check_url. If auth required, send Telegram and poll until
    the user logs in via the open Chrome window or timeout expires.

    Returns True  — authenticated, safe to proceed
    Returns False — timed out, caller should raise SystemExit(10)
    """
    try:
        page.goto(check_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"[auth_check] Navigation error for {provider}: {e}", file=sys.stderr, flush=True)
        return False

    if not is_auth_page_fn(page.url):
        print(f"[auth_check] {provider}: authenticated ✓", flush=True)
        return True

    # Auth required — notify and wait
    _notify(
        f"⚠️ Auth required: {provider}\n"
        f"Please log in in the Chrome window.\n"
        f"Pipeline will continue automatically once logged in.\n"
        f"Timeout: {timeout_sec // 60} min."
    )
    print(
        f"\n⚠️  AUTH REQUIRED: {provider}. "
        f"Log in to Chrome. Waiting up to {timeout_sec}s...",
        flush=True,
    )

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(poll_sec)
        try:
            current_url = page.url
        except Exception:
            current_url = ""

        if not is_auth_page_fn(current_url):
            print(f"✅ {provider}: login detected, continuing.", flush=True)
            _notify(f"✅ {provider} authenticated — pipeline resuming.")
            return True

        remaining = int(deadline - time.time())
        print(f"  [{provider}] still waiting... {remaining}s left", flush=True)

    print(f"❌ {provider}: auth timed out after {timeout_sec}s.", file=sys.stderr, flush=True)
    _notify(f"❌ {provider} auth timed out ({timeout_sec // 60} min). Provider skipped.")
    return False
