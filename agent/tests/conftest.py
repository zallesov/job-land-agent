from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.fake_mcp import FakeMCPClient


@pytest.fixture
def mcp(monkeypatch):
    """In-memory MCP client double. Never touches the network or the MCP server."""
    fake = FakeMCPClient()
    monkeypatch.setattr("scripts.mcp_client.get_client", lambda: fake)
    return fake


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end test requiring live Chrome + Hermes + a local PocketBase instance")
