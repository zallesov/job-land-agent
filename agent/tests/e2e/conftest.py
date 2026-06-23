"""Safety guard: e2e tests write real records via PBClient. Refuse to run
against anything but a local PocketBase instance, so a stray `pytest -m e2e`
can never touch the production database at POCKETBASE_URL.
"""
from __future__ import annotations
import os

import pytest

_LOCAL_HOSTS = ("localhost", "127.0.0.1")


@pytest.fixture(scope="session", autouse=True)
def _require_local_pocketbase():
    url = os.environ.get("POCKETBASE_URL", "")
    if not any(host in url for host in _LOCAL_HOSTS):
        pytest.skip(
            f"refusing to run e2e tests against non-local POCKETBASE_URL={url!r}. "
            "Start a local PocketBase instance and set POCKETBASE_URL=http://localhost:8090 "
            "(plus POCKETBASE_ADMIN_EMAIL/PASSWORD) before running -m e2e."
        )
