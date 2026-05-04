"""Tests for agent_inspect_cmd in uio.cli.agent."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from uio.cli.agent import agent_inspect_cmd


_AGENT_MD = """\
---
name: test-agent
description: A minimal test agent
complexity: small
---

Body line one.
"""


def _cfg(tmp_path):
    return {
        "dirs": {"agents": str(tmp_path)},
        "large_agents": {"names": []},
    }


def test_agent_inspect_calls_load_config_once(tmp_path):
    (tmp_path / "test-agent.agent.md").write_text(_AGENT_MD)
    with patch("uio.cli.agent.load_config", return_value=_cfg(tmp_path)) as mock_cfg:
        result = CliRunner().invoke(agent_inspect_cmd, ["test-agent"])

    assert result.exit_code == 0
    assert "Complexity:" in result.output
    mock_cfg.assert_called_once()


def test_agent_inspect_output_fields(tmp_path):
    (tmp_path / "test-agent.agent.md").write_text(_AGENT_MD)
    with patch("uio.cli.agent.load_config", return_value=_cfg(tmp_path)):
        result = CliRunner().invoke(agent_inspect_cmd, ["test-agent"])

    assert result.exit_code == 0
    assert "Name:" in result.output
    assert "Description:" in result.output
    assert "Complexity:" in result.output


def test_agent_inspect_missing_agent_exits_nonzero(tmp_path):
    with patch("uio.cli.agent.load_config", return_value=_cfg(tmp_path)):
        result = CliRunner().invoke(agent_inspect_cmd, ["no-such-agent"])

    assert result.exit_code != 0
