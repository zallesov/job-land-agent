#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import yaml


DEFAULT_TEMPLATE_DIR = Path("/opt/joblandagent/profile-template")
DEFAULT_PROFILE_DIR = Path("/opt/data/profiles/joblandagent")
DEFAULT_UID = 10010
DEFAULT_GID = 10010


def load_distribution_owned(template_dir: Path) -> list[str]:
    distribution_path = template_dir / "distribution.yaml"
    distribution = yaml.safe_load(distribution_path.read_text()) or {}
    owned = distribution.get("distribution_owned") or []
    if not isinstance(owned, list):
        raise ValueError("distribution_owned must be a list")
    return [str(entry).strip().strip("/") for entry in owned if str(entry).strip()]


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_directory_overlay(src: Path, dst: Path) -> None:
    for path in src.rglob("*"):
        relative = path.relative_to(src)
        target = dst / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            copy_file(path, target)


def copy_distribution_entry(template_dir: Path, profile_dir: Path, entry: str) -> None:
    src = template_dir / entry
    dst = profile_dir / entry
    if not src.exists():
        raise FileNotFoundError(f"distribution entry does not exist in template: {entry}")
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        copy_directory_overlay(src, dst)
    elif src.is_file():
        copy_file(src, dst)
    else:
        raise ValueError(f"unsupported distribution entry type: {entry}")


def merge_mcp_config(profile_dir: Path, mcp_json_path: Path) -> None:
    if not mcp_json_path.exists():
        return

    config_path = profile_dir / "config.yaml"
    config: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text())
        if isinstance(loaded, dict):
            config = loaded

    mcp_config = json.loads(mcp_json_path.read_text())
    mcp_servers = mcp_config.get("mcp_servers") or {}
    if not isinstance(mcp_servers, dict):
        raise ValueError("mcp.json mcp_servers must be an object")

    servers = config.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        raise ValueError("config.yaml mcp_servers must be a mapping")
    servers.update(mcp_servers)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))


def read_existing_mcp_servers(profile_dir: Path) -> dict[str, Any]:
    config_path = profile_dir / "config.yaml"
    if not config_path.exists():
        return {}
    loaded = yaml.safe_load(config_path.read_text()) or {}
    if not isinstance(loaded, dict):
        return {}
    servers = loaded.get("mcp_servers") or {}
    return servers if isinstance(servers, dict) else {}


def chown_tree(path: Path, uid: int, gid: int) -> None:
    if uid < 0 or gid < 0 or not path.exists():
        return
    for item in [path, *path.rglob("*")]:
        try:
            os.chown(item, uid, gid)
        except PermissionError:
            pass


def sync_profile(template_dir: Path, profile_dir: Path) -> None:
    profile_dir.mkdir(parents=True, exist_ok=True)
    existing_mcp_servers = read_existing_mcp_servers(profile_dir)
    for entry in load_distribution_owned(template_dir):
        copy_distribution_entry(template_dir, profile_dir, entry)
    if existing_mcp_servers:
        config_path = profile_dir / "config.yaml"
        config = yaml.safe_load(config_path.read_text()) or {}
        servers = config.setdefault("mcp_servers", {})
        servers.update(existing_mcp_servers)
        config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True))
    merge_mcp_config(profile_dir, template_dir / "mcp.json")


def env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def main() -> None:
    template_dir = env_path("JOBLAND_PROFILE_TEMPLATE_DIR", DEFAULT_TEMPLATE_DIR)
    profile_dir = env_path("JOBLAND_PROFILE_DIR", DEFAULT_PROFILE_DIR)
    uid = env_int("HERMES_UID", DEFAULT_UID)
    gid = env_int("HERMES_GID", DEFAULT_GID)

    sync_profile(template_dir, profile_dir)
    chown_tree(profile_dir, uid, gid)
    print(f"synced JobLandAgent profile distribution to {profile_dir}")


if __name__ == "__main__":
    main()
