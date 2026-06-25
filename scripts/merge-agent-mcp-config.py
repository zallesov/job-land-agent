#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml


PROFILE_DIR = Path(os.environ.get("JOBLAND_PROFILE_DIR", "/opt/data/profiles/joblandagent"))
MCP_JSON = Path(os.environ.get("JOBLAND_MCP_JSON", "/tmp/joblandagent-mcp.json"))
TOKEN_ENV = "MCP_JOBLAND_API_KEY"


def upsert_env_var(path: Path, key: str, value: str) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    out: list[str] = []
    seen = False

    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            seen = True
        else:
            out.append(line)

    if not seen:
        if out and out[-1].strip():
            out.append("")
        out.append(f"{key}={value}")

    path.write_text("\n".join(out) + "\n")


def main() -> None:
    token = os.environ.get(TOKEN_ENV, "")

    config_path = PROFILE_DIR / "config.yaml"
    env_path = PROFILE_DIR / ".env"

    config = yaml.safe_load(config_path.read_text()) or {}
    mcp_config = json.loads(MCP_JSON.read_text())

    servers = config.setdefault("mcp_servers", {})
    servers.update(mcp_config.get("mcp_servers", {}))

    config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    if token:
        upsert_env_var(env_path, TOKEN_ENV, token)
    elif f"{TOKEN_ENV}=" not in (env_path.read_text() if env_path.exists() else ""):
        raise SystemExit(f"{TOKEN_ENV} is not set locally or in {env_path}")

    for path in (config_path, env_path):
        try:
            os.chown(path, 10010, 10010)
        except PermissionError:
            pass

    print(f"updated {config_path}")


if __name__ == "__main__":
    main()
