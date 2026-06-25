from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_PATH = REPO_ROOT / "docker" / "hermes-agent" / "bootstrap-profile.py"


def load_bootstrap_module():
    assert BOOTSTRAP_PATH.exists(), "bootstrap script should exist"
    spec = importlib.util.spec_from_file_location("hermes_profile_bootstrap", BOOTSTRAP_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_sync_profile_updates_distribution_owned_files_and_preserves_runtime_state(tmp_path: Path) -> None:
    bootstrap = load_bootstrap_module()
    template = tmp_path / "template"
    profile = tmp_path / "profile"

    write(
        template / "distribution.yaml",
        "\n".join(
            [
                "name: joblandagent",
                "distribution_owned:",
                "- distribution.yaml",
                "- config.yaml",
                "- mcp.json",
                "- scripts",
                "",
            ]
        ),
    )
    write(template / "config.yaml", "model:\n  default: gpt-5.4\n")
    write(
        template / "mcp.json",
        '{"mcp_servers":{"jobland":{"url":"https://mcp.zall.dev/mcp","enabled":true}}}',
    )
    write(template / "scripts" / "tool.py", "print('new tool')\n")

    write(profile / ".env", "SECRET=keep-me\n")
    write(profile / "config" / "user.yaml", "name: keep-user-config\n")
    write(profile / "state.db", "keep-state\n")
    write(profile / "logs" / "agent.log", "keep-log\n")
    write(profile / "scripts" / "runtime-note.txt", "keep-runtime-note\n")
    write(profile / "scripts" / "tool.py", "print('old tool')\n")

    bootstrap.sync_profile(template, profile)

    assert (profile / "distribution.yaml").read_text() == (template / "distribution.yaml").read_text()
    assert (profile / "scripts" / "tool.py").read_text() == "print('new tool')\n"
    assert (profile / "scripts" / "runtime-note.txt").read_text() == "keep-runtime-note\n"
    assert (profile / ".env").read_text() == "SECRET=keep-me\n"
    assert (profile / "config" / "user.yaml").read_text() == "name: keep-user-config\n"
    assert (profile / "state.db").read_text() == "keep-state\n"
    assert (profile / "logs" / "agent.log").read_text() == "keep-log\n"


def test_sync_profile_merges_jobland_mcp_config_into_profile_config(tmp_path: Path) -> None:
    bootstrap = load_bootstrap_module()
    template = tmp_path / "template"
    profile = tmp_path / "profile"

    write(
        template / "distribution.yaml",
        "\n".join(
            [
                "name: joblandagent",
                "distribution_owned:",
                "- distribution.yaml",
                "- config.yaml",
                "- mcp.json",
                "",
            ]
        ),
    )
    write(template / "config.yaml", "model:\n  default: gpt-5.4\n")
    write(
        template / "mcp.json",
        "\n".join(
            [
                "{",
                '  "mcp_servers": {',
                '    "jobland": {',
                '      "url": "https://mcp.zall.dev/mcp",',
                '      "headers": {"Authorization": "Bearer ${MCP_JOBLAND_API_KEY}"},',
                '      "enabled": true',
                "    }",
                "  }",
                "}",
                "",
            ]
        ),
    )
    write(
        profile / "config.yaml",
        "\n".join(
            [
                "model:",
                "  default: gpt-5.4",
                "mcp_servers:",
                "  existing:",
                "    url: https://example.test/mcp",
                "",
            ]
        ),
    )

    bootstrap.sync_profile(template, profile)

    config = bootstrap.yaml.safe_load((profile / "config.yaml").read_text())
    assert config["model"]["default"] == "gpt-5.4"
    assert config["mcp_servers"]["existing"]["url"] == "https://example.test/mcp"
    assert config["mcp_servers"]["jobland"]["url"] == "https://mcp.zall.dev/mcp"
    assert (
        config["mcp_servers"]["jobland"]["headers"]["Authorization"]
        == "Bearer ${MCP_JOBLAND_API_KEY}"
    )
