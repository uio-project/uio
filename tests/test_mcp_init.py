"""Tests for `uio mcp init`."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from uio.cli.main import main

_TOML_GITHUB = """\
[mcp.github]
command  = "github-mcp-server stdio"
env_keys = ["GITHUB_PERSONAL_ACCESS_TOKEN"]
"""

_TOML_TWO_SERVERS = """\
[mcp.github]
command  = "github-mcp-server stdio"
env_keys = ["GITHUB_PERSONAL_ACCESS_TOKEN"]

[mcp.git]
command  = "uvx mcp-server-git --repository /workspace"
"""

_TOML_NO_ENV = """\
[mcp.git]
command = "uvx mcp-server-git --repository /workspace"
"""


def _run(args: list[str], toml: str | None = _TOML_GITHUB) -> object:
    runner = CliRunner()
    with runner.isolated_filesystem():
        if toml is not None:
            Path("uio.toml").write_text(toml)
        result = runner.invoke(main, ["mcp"] + args, catch_exceptions=False)
    return result


# ---------------------------------------------------------------------------
# Claude output format
# ---------------------------------------------------------------------------


def test_claude_writes_mcp_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        result = runner.invoke(main, ["mcp", "init", "--for", "claude"], catch_exceptions=False)
        assert result.exit_code == 0
        data = json.loads(Path(".mcp.json").read_text())

    assert "mcpServers" in data
    gh = data["mcpServers"]["github"]
    assert gh["command"] == "github-mcp-server"
    assert gh["args"] == ["stdio"]
    assert gh["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "${GITHUB_PERSONAL_ACCESS_TOKEN}"


def test_claude_no_env_keys_omits_env_block():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_NO_ENV)
        runner.invoke(main, ["mcp", "init", "--for", "claude"], catch_exceptions=False)
        data = json.loads(Path(".mcp.json").read_text())

    assert "env" not in data["mcpServers"]["git"]


# ---------------------------------------------------------------------------
# VS Code output format
# ---------------------------------------------------------------------------


def test_vscode_writes_vscode_mcp_json():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        result = runner.invoke(main, ["mcp", "init", "--for", "vscode"], catch_exceptions=False)
        assert result.exit_code == 0
        data = json.loads(Path(".vscode/mcp.json").read_text())

    assert "servers" in data
    gh = data["servers"]["github"]
    assert gh["command"] == "github-mcp-server"
    assert gh["args"] == ["stdio"]
    assert gh["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "${input:github-personal-access-token}"

    assert data["inputs"][0]["id"] == "github-personal-access-token"
    assert data["inputs"][0]["password"] is True


def test_vscode_creates_directory():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        runner.invoke(main, ["mcp", "init", "--for", "vscode"], catch_exceptions=False)
        assert Path(".vscode/mcp.json").exists()


def test_vscode_no_env_keys_omits_inputs():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_NO_ENV)
        runner.invoke(main, ["mcp", "init", "--for", "vscode"], catch_exceptions=False)
        data = json.loads(Path(".vscode/mcp.json").read_text())

    assert "inputs" not in data


# ---------------------------------------------------------------------------
# Skip-if-exists / --force
# ---------------------------------------------------------------------------


def test_skip_if_exists():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        Path(".mcp.json").write_text('{"original": true}')
        result = runner.invoke(main, ["mcp", "init", "--for", "claude"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Skipped" in result.output
        assert json.loads(Path(".mcp.json").read_text()) == {"original": True}


def test_force_overwrites():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        Path(".mcp.json").write_text('{"original": true}')
        result = runner.invoke(
            main, ["mcp", "init", "--for", "claude", "--force"], catch_exceptions=False
        )
        assert result.exit_code == 0
        data = json.loads(Path(".mcp.json").read_text())
        assert "mcpServers" in data


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------


def test_dry_run_makes_no_changes():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        result = runner.invoke(
            main, ["mcp", "init", "--for", "claude", "--dry-run"], catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "Would write" in result.output
        assert not Path(".mcp.json").exists()


# ---------------------------------------------------------------------------
# No MCP config
# ---------------------------------------------------------------------------


def test_no_mcp_config_exits_nonzero():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["mcp", "init", "--for", "claude"])
        assert result.exit_code != 0
        assert "No MCP servers configured" in result.output


# ---------------------------------------------------------------------------
# --global flag
# ---------------------------------------------------------------------------


def test_global_writes_claude_settings(tmp_path):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        with patch("uio.cli.mcp.Path.home", return_value=fake_home):
            result = runner.invoke(
                main, ["mcp", "init", "--for", "claude", "--global"], catch_exceptions=False
            )
    assert result.exit_code == 0
    settings = json.loads((fake_home / ".claude" / "settings.json").read_text())
    assert "mcpServers" in settings
    assert "github" in settings["mcpServers"]


def test_global_merges_existing_claude_settings(tmp_path):
    fake_home = tmp_path / "home"
    (fake_home / ".claude").mkdir(parents=True)
    existing = {"theme": "dark", "mcpServers": {"other": {"command": "other-server"}}}
    (fake_home / ".claude" / "settings.json").write_text(json.dumps(existing))

    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        with patch("uio.cli.mcp.Path.home", return_value=fake_home):
            runner.invoke(
                main, ["mcp", "init", "--for", "claude", "--global"], catch_exceptions=False
            )

    settings = json.loads((fake_home / ".claude" / "settings.json").read_text())
    assert settings["theme"] == "dark"
    assert "other" in settings["mcpServers"]
    assert "github" in settings["mcpServers"]


def test_global_with_vscode_exits_nonzero():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        result = runner.invoke(main, ["mcp", "init", "--for", "vscode", "--global"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# --for is required
# ---------------------------------------------------------------------------


def test_for_required():
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("uio.toml").write_text(_TOML_GITHUB)
        result = runner.invoke(main, ["mcp", "init"])
        assert result.exit_code != 0
