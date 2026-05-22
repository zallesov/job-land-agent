from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

from .types import HermesResult

PROJECT_ROOT = Path(__file__).parent.parent.parent
CV_PATH = PROJECT_ROOT / "cv_master_content.md"


def _find_hermes_venv_python() -> Path | None:
    """Locate the Hermes venv Python regardless of $HOME sandboxing.

    Hermes sandboxes $HOME inside its agent runs, so Path.home() is wrong.
    Instead read the hermes wrapper script to get the absolute venv path.
    """
    # Try reading the wrapper script (which contains the absolute venv path)
    try:
        which = subprocess.run(["which", "hermes"], capture_output=True, text=True)
        wrapper = Path(which.stdout.strip())
        if wrapper.exists():
            content = wrapper.read_text()
            m = re.search(r'exec\s+"([^"]+/hermes-agent/venv)/bin/hermes"', content)
            if m:
                py = Path(m.group(1)) / "bin" / "python"
                if py.exists():
                    return py
    except Exception:
        pass
    # Absolute fallback (known install location)
    candidate = Path("/Users/zall/.hermes/hermes-agent/venv/bin/python")
    return candidate if candidate.exists() else None


_HERMES_VENV_PYTHON = _find_hermes_venv_python()
_HERMES_DIR = _HERMES_VENV_PYTHON.parent.parent.parent if _HERMES_VENV_PYTHON else None


def build_prompt(skill: str, context: dict) -> str:
    parts = [f"Use skill {skill}."]
    for k, v in context.items():
        parts.append(f"{k}: {v}.")
    return " ".join(parts)


def _run_via_venv(prompt: str, timeout_sec: int) -> str:
    """Run Hermes agent using its own venv Python to avoid dep conflicts."""
    script = f"""
import sys
sys.path.insert(0, {str(_HERMES_DIR)!r})
from run_agent import AIAgent
agent = AIAgent(quiet_mode=True, skip_context_files=True, max_iterations=10)
result = agent.chat({prompt!r})
print(result)
"""
    proc = subprocess.run(
        [str(_HERMES_VENV_PYTHON), "-c", script],
        capture_output=True, text=True, timeout=timeout_sec,
        cwd=str(PROJECT_ROOT),
    )
    return proc.stdout + proc.stderr


def hermes_call(skill: str, context: dict, timeout_sec: int = 300) -> HermesResult:
    if _HERMES_VENV_PYTHON is None:
        return HermesResult(
            success=False, data={}, error="run_agent (Hermes) is not installed", raw_output=""
        )
    prompt = build_prompt(skill, context)
    try:
        raw = _run_via_venv(prompt, timeout_sec)
    except subprocess.TimeoutExpired:
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
