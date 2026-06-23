from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

from .types import HermesResult

PROJECT_ROOT = Path(__file__).parent.parent.parent
HERMES_PROFILE = os.environ.get("HERMES_PROFILE", "joblandagent")
_PROFILE_HOME = Path.home() / ".hermes" / "profiles" / HERMES_PROFILE
AIAgent = None


def _find_hermes_venv_python() -> Path | None:
    """Locate the Hermes venv Python regardless of $HOME sandboxing."""
    try:
        hermes_bin = shutil.which("hermes")
        wrapper = Path(hermes_bin) if hermes_bin else None
        if wrapper and wrapper.exists():
            content = wrapper.read_text()
            m = re.search(r'exec\s+"([^"]+/hermes-agent/venv)/bin/hermes"', content)
            if m:
                py = Path(m.group(1)) / "bin" / "python"
                if py.exists():
                    return py
    except Exception:
        pass
    return None


_HERMES_VENV_PYTHON = _find_hermes_venv_python()
_HERMES_DIR = _HERMES_VENV_PYTHON.parent.parent.parent if _HERMES_VENV_PYTHON else None


def _resolve_hermes_model() -> tuple[str, str]:
    """Read model.default and model.provider from the joblandagent profile config."""
    for config_path in [
        _PROFILE_HOME / "config.yaml",
        Path.home() / ".hermes" / "config.yaml",
    ]:
        if config_path.exists():
            try:
                data = yaml.safe_load(config_path.read_text()) or {}
                m = data.get("model", {})
                model = str(m.get("default", ""))
                provider = str(m.get("provider", ""))
                if model:
                    return model, provider
            except Exception:
                pass
    return "", ""


def build_prompt(skill: str, context: dict) -> str:
    parts = [f"Use skill {skill}."]
    for k, v in context.items():
        parts.append(f"{k}: {v}.")
    return " ".join(parts)


def _profile_home() -> Path | None:
    return _PROFILE_HOME if _PROFILE_HOME.exists() else None


def _run_via_venv(prompt: str, timeout_sec: int) -> str:
    """Run Hermes agent using its own venv Python to avoid dep conflicts."""
    model, provider = _resolve_hermes_model()
    script = f"""
import sys
sys.path.insert(0, {str(_HERMES_DIR)!r})
from run_agent import AIAgent
agent = AIAgent(
    quiet_mode=True,
    skip_context_files=True,
    max_iterations=10,
    model={model!r},
    provider={provider!r},
)
result = agent.chat({prompt!r})
print(result)
"""
    env = None
    ph = _profile_home()
    if ph:
        import os
        env = {**os.environ, "HERMES_HOME": str(ph)}

    proc = subprocess.run(
        [str(_HERMES_VENV_PYTHON), "-c", script],
        capture_output=True, text=True, timeout=timeout_sec,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    return proc.stdout + proc.stderr


def hermes_call(skill: str, context: dict, timeout_sec: int = 300) -> HermesResult:
    if AIAgent is not None:
        prompt = build_prompt(skill, context)
        try:
            agent = AIAgent(quiet_mode=True, skip_context_files=True, max_iterations=10)
            raw = agent.chat(prompt)
        except TimeoutError:
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
