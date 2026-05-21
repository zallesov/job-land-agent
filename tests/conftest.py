from __future__ import annotations
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.db import create_db, get_connection


@pytest.fixture
def db_path(tmp_path):
    p = str(tmp_path / "test.db")
    create_db(p)
    return p


@pytest.fixture
def con(db_path):
    c = get_connection(db_path)
    yield c
    c.close()


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end test requiring live Chrome + Hermes")
