from __future__ import annotations
import json
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path

from .types import HermesResult

PROJECT_ROOT = Path(__file__).parent.parent.parent
CV_PATH = PROJECT_ROOT / "cv_master_content.md"

try:
    from run_agent import AIAgent  # Hermes Python library
except ImportError:  # not available in test environments
    AIAgent = None  # type: ignore[assignment,misc]


def build_prompt(skill: str, context: dict) -> str:
    parts = [f"Use skill {skill}."]
    for k, v in context.items():
        parts.append(f"{k}: {v}.")
    return " ".join(parts)


def hermes_call(skill: str, context: dict, timeout_sec: int = 300) -> HermesResult:
    if AIAgent is None:
        return HermesResult(
            success=False, data={}, error="run_agent (Hermes) is not installed", raw_output=""
        )
    prompt = build_prompt(skill, context)
    try:
        agent = AIAgent(quiet_mode=True, skip_context_files=True, max_iterations=10)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(agent.chat, prompt)
            raw = future.result(timeout=timeout_sec)
    except FuturesTimeoutError:
        return HermesResult(
            success=False, data={}, error=f"timeout after {timeout_sec}s", raw_output=""
        )
    except Exception as e:
        return HermesResult(success=False, data={}, error=str(e), raw_output="")

    try:
        s = raw
        data = json.loads(s[s.index("{") : s.rindex("}") + 1])
        success = data.get("status") == "success"
        return HermesResult(
            success=success, data=data, error=data.get("error"), raw_output=raw
        )
    except Exception as e:
        return HermesResult(
            success=False, data={}, error=f"parse error: {e}", raw_output=raw
        )
