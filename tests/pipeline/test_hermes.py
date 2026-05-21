from __future__ import annotations
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures" / "hermes"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


@patch("scripts.pipeline.hermes.AIAgent")
def test_success(mock_cls):
    raw = _load("enrich_success.json")
    mock_cls.return_value.chat.return_value = raw
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is True
    assert result.data["title"] == "Senior Engineer"
    assert result.error is None


@patch("scripts.pipeline.hermes.AIAgent")
def test_failure_json(mock_cls):
    raw = _load("enrich_failure.json")
    mock_cls.return_value.chat.return_value = raw
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is False
    assert result.error == "login wall"


@patch("scripts.pipeline.hermes.AIAgent")
def test_exception_returns_failure(mock_cls):
    mock_cls.return_value.chat.side_effect = RuntimeError("boom")
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is False
    assert "boom" in result.error


@patch("scripts.pipeline.hermes.AIAgent")
def test_timeout_returns_failure(mock_cls):
    from concurrent.futures import TimeoutError as FTE
    mock_cls.return_value.chat.side_effect = FTE()
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"}, timeout_sec=1)
    assert result.success is False
    assert "timeout" in result.error


@patch("scripts.pipeline.hermes.AIAgent")
def test_unparseable_json(mock_cls):
    mock_cls.return_value.chat.return_value = "no json here"
    from scripts.pipeline.hermes import hermes_call
    result = hermes_call("enrich-job", {"job_id": 1, "url": "https://x.com"})
    assert result.success is False
    assert "parse error" in result.error


def test_build_prompt():
    from scripts.pipeline.hermes import build_prompt
    p = build_prompt("enrich-job", {"job_id": 42, "url": "https://x.com"})
    assert p == "Use skill enrich-job. job_id: 42. url: https://x.com"
