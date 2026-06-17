from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.fake_pb import FakePBClient


@pytest.fixture
def pb(monkeypatch):
    """In-memory PocketBase double. Never touches the network or real PocketBase."""
    fake = FakePBClient()
    monkeypatch.setattr("scripts.pb_client.get_pb", lambda: fake)
    return fake


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end test requiring live Chrome + Hermes + a local PocketBase instance")
