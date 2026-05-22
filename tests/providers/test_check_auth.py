"""
E2E auth checks — requires Chrome running at localhost:9222.

Run:  pytest tests/providers/test_check_auth.py -m e2e -v -s
      (use -s so auth prompts print to terminal)

If a provider is not logged in, wait_for_auth sends a Telegram notification
and waits up to 10 minutes for you to log in via the open Chrome window.
"""
from __future__ import annotations
import subprocess
import time
import urllib.request

import pytest

CDP_URL = "http://localhost:9222"
START_CHROME = str(__import__("pathlib").Path.home() / "start-chrome.sh")


def _chrome_ready(timeout: int = 15) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


@pytest.fixture(scope="module", autouse=True)
def ensure_chrome():
    """Start Chrome if not already running."""
    if not _chrome_ready(timeout=3):
        print("\nChrome not running — launching via start-chrome.sh...")
        subprocess.Popen(["bash", START_CHROME], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert _chrome_ready(timeout=15), "Chrome did not start within 15s"
        print("Chrome ready.")


@pytest.mark.e2e
def test_greenhouse_check_auth():
    from scripts.providers.greenhouse.check_auth import check_auth
    check_auth(CDP_URL)  # raises AuthError if auth fails


@pytest.mark.e2e
def test_jobleads_check_auth():
    from scripts.providers.jobleads.check_auth import check_auth
    check_auth(CDP_URL)


@pytest.mark.e2e
def test_wellfound_check_auth():
    from scripts.providers.wellfound.check_auth import check_auth
    check_auth(CDP_URL)


@pytest.mark.e2e
def test_sprout_check_auth():
    from scripts.providers.sprout.check_auth import check_auth
    check_auth(CDP_URL)


@pytest.mark.e2e
def test_hirify_check_auth():
    from scripts.providers.hirify.check_auth import check_auth
    check_auth(CDP_URL)
