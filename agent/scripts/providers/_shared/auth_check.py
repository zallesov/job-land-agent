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
    """Navigate to check_url; if auth required, notify via Telegram and poll.

    Returns True on success, False on timeout (caller raises AuthError).
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

    _notify(
        f"⚠️ Auth required: {provider}\n"
        f"Log in in the Chrome window.\n"
        f"Timeout: {timeout_sec // 60} min."
    )
    print(f"\n⚠️  AUTH REQUIRED: {provider}. Waiting up to {timeout_sec}s...", flush=True)

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        time.sleep(poll_sec)
        try:
            current_url = page.url
        except Exception:
            current_url = ""
        if not is_auth_page_fn(current_url):
            print(f"✅ {provider}: login detected.", flush=True)
            _notify(f"✅ {provider} authenticated — pipeline resuming.")
            return True
        remaining = int(deadline - time.time())
        print(f"  [{provider}] still waiting... {remaining}s left", flush=True)

    print(f"❌ {provider}: auth timed out.", file=sys.stderr, flush=True)
    _notify(f"❌ {provider} auth timed out ({timeout_sec // 60} min). Provider skipped.")
    return False
