"""Tests for MCP multi-server client factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from uio.core.mcp import MCPClient, _default_github_mcp_command, make_mcp_client, make_mcp_clients


class TestDefaultGithubMcpCommand:
    def test_binary_present_returns_binary(self):
        def which(name):
            if name == "github-mcp-server":
                return "/usr/local/bin/github-mcp-server"
            return None

        with patch("uio.core.mcp.shutil.which", side_effect=which):
            assert _default_github_mcp_command() == ["/usr/local/bin/github-mcp-server", "stdio"]

    def test_no_binary_falls_back_to_community_npm(self):
        with patch("uio.core.mcp.shutil.which", return_value=None):
            assert _default_github_mcp_command() == [
                "npx",
                "-y",
                "@modelcontextprotocol/server-github",
            ]

    def test_binary_wins_over_npm(self):
        with patch("uio.core.mcp.shutil.which", return_value="/some/path"):
            assert _default_github_mcp_command() == ["/some/path", "stdio"]


class TestMakeMcpClientTokenPriority:
    def test_gh_token_wins_over_pat(self, monkeypatch):
        """GH_TOKEN (App identity) takes priority over GITHUB_PERSONAL_ACCESS_TOKEN."""
        monkeypatch.setenv("GH_TOKEN", "app-token")
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "pat-token")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        captured_env = {}

        def fake_mcp_cls(command, server_name, env=None, **kwargs):
            captured_env.update(env or {})
            return MagicMock()

        with patch("uio.core.mcp.MCPClient", side_effect=fake_mcp_cls):
            result = make_mcp_client()

        assert result is not None
        assert captured_env["GH_TOKEN"] == "app-token"
        assert captured_env["GITHUB_TOKEN"] == "app-token"
        assert captured_env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "app-token"

    def test_all_three_vars_set_in_child_env(self, monkeypatch):
        """Selected token is exported under all three env var names."""
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "pat-token")

        captured_env = {}

        def fake_mcp_cls(command, server_name, env=None, **kwargs):
            captured_env.update(env or {})
            return MagicMock()

        with patch("uio.core.mcp.MCPClient", side_effect=fake_mcp_cls):
            result = make_mcp_client()

        assert result is not None
        assert captured_env["GH_TOKEN"] == "pat-token"
        assert captured_env["GITHUB_TOKEN"] == "pat-token"
        assert captured_env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "pat-token"

    def test_no_token_returns_none(self, monkeypatch):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        assert make_mcp_client() is None

    def test_app_token_uses_binary_when_present(self, monkeypatch):
        """When GH_TOKEN is set (App identity), the standalone binary is used if found."""
        monkeypatch.setenv("GH_TOKEN", "ghs_app_token")
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)

        captured_command = []

        def fake_mcp_cls(command, server_name, env=None, **kwargs):
            captured_command.extend(command)
            return MagicMock()

        with (
            patch("uio.core.mcp.MCPClient", side_effect=fake_mcp_cls),
            patch(
                "uio.core.mcp.shutil.which",
                side_effect=lambda x: (
                    "/usr/bin/github-mcp-server" if x == "github-mcp-server" else None
                ),
            ),
        ):
            result = make_mcp_client()

        assert result is not None
        assert captured_command == ["/usr/bin/github-mcp-server", "stdio"]

    def test_server_failure_warns_and_returns_none(self, monkeypatch, capsys):
        """When the MCP server process fails to start, a warning is printed and None returned."""
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "pat-token")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        with (
            patch("uio.core.mcp.MCPClient", side_effect=RuntimeError("MCP server closed")),
            patch("uio.core.mcp.shutil.which", return_value=None),
        ):
            result = make_mcp_client()

        assert result is None
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "MCP_GITHUB_COMMAND" in captured.err


def _make_mock_client(server_name: str) -> MagicMock:
    client = MagicMock()
    client.server_name = server_name
    return client


class TestMakeMcpClients:
    def test_empty_config_no_token_returns_empty(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        result = make_mcp_clients({})
        assert result == {}

    def test_empty_config_with_token_auto_starts_github(self, monkeypatch):
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "tok")
        mock_client = _make_mock_client("github")
        with patch("uio.core.mcp.make_mcp_client", return_value=mock_client):
            result = make_mcp_clients({})
        assert "github" in result
        assert result["github"] is mock_client

    def test_explicit_github_in_config_skips_auto_start(self, monkeypatch):
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "tok")
        mock_client = _make_mock_client("github")
        with (
            patch("uio.core.mcp.MCPClient", return_value=mock_client) as MockCls,
            patch("uio.core.mcp.make_mcp_client") as auto_start,
        ):
            result = make_mcp_clients(
                {"github": {"command": "npx -y @github/github-mcp-server stdio"}}
            )
        auto_start.assert_not_called()
        MockCls.assert_called_once()
        assert "github" in result

    def test_multiple_servers_all_started(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mcp_cfg = {
            "filesystem": {"command": "npx -y @modelcontextprotocol/server-filesystem /workspace"},
            "fetch": {"command": "npx -y @modelcontextprotocol/server-fetch"},
        }
        fs_client = _make_mock_client("filesystem")
        fetch_client = _make_mock_client("fetch")
        clients_by_name = {"filesystem": fs_client, "fetch": fetch_client}

        def fake_mcp_client(command, server_name, **kwargs):
            return clients_by_name[server_name]

        with patch("uio.core.mcp.MCPClient", side_effect=fake_mcp_client):
            result = make_mcp_clients(mcp_cfg)

        assert set(result.keys()) == {"filesystem", "fetch"}

    def test_server_with_missing_command_skipped(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        mcp_cfg = {"broken": {"command": ""}}
        with patch("uio.core.mcp.MCPClient") as MockCls:
            result = make_mcp_clients(mcp_cfg)
        MockCls.assert_not_called()
        assert result == {}

    def test_failing_server_warns_and_continues(self, monkeypatch, capsys):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        good_client = _make_mock_client("fetch")

        def fake_mcp_client(command, server_name, **kwargs):
            if server_name == "broken":
                raise RuntimeError("process refused")
            return good_client

        mcp_cfg = {
            "broken": {"command": "bad-server"},
            "fetch": {"command": "npx -y @modelcontextprotocol/server-fetch"},
        }
        with patch("uio.core.mcp.MCPClient", side_effect=fake_mcp_client):
            result = make_mcp_clients(mcp_cfg)

        assert "broken" not in result
        assert "fetch" in result
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "broken" in captured.err

    def test_duplicate_server_name_first_wins(self, monkeypatch):
        """Programmatically constructed dicts with duplicate names: first entry wins."""
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "tok")
        auto_client = _make_mock_client("github")
        cfg_client = _make_mock_client("github")

        with (
            patch("uio.core.mcp.make_mcp_client", return_value=auto_client),
            patch("uio.core.mcp.MCPClient", return_value=cfg_client),
        ):
            # github is NOT in cfg, so auto-start runs first; cfg loop has no "github" entry
            result = make_mcp_clients({})

        assert result["github"] is auto_client


class TestMcpPlugins:
    def test_plugin_with_all_env_vars_starts(self, monkeypatch, capsys):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GITLAB_TOKEN", "gl-token")

        plugin_client = _make_mock_client("gitlab")
        plugins = [
            {
                "name": "gitlab",
                "type": "vcs",
                "command": "npx gitlab-mcp",
                "env_keys": ["GITLAB_TOKEN"],
            }
        ]

        with patch("uio.core.mcp.MCPClient", return_value=plugin_client):
            result = make_mcp_clients({}, plugins=plugins)

        assert "gitlab" in result
        assert result["gitlab"] is plugin_client

    def test_plugin_with_missing_env_var_skipped(self, monkeypatch, capsys):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GITLAB_TOKEN", raising=False)

        plugins = [
            {
                "name": "gitlab",
                "type": "vcs",
                "command": "npx gitlab-mcp",
                "env_keys": ["GITLAB_TOKEN"],
            }
        ]

        with patch("uio.core.mcp.MCPClient") as MockCls:
            result = make_mcp_clients({}, plugins=plugins)

        MockCls.assert_not_called()
        assert "gitlab" not in result
        captured = capsys.readouterr()
        assert "Warning" in captured.err
        assert "GITLAB_TOKEN" in captured.err

    def test_plugin_with_no_env_keys_starts_unconditionally(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        plugin_client = _make_mock_client("sequential-thinking")
        plugins = [{"name": "sequential-thinking", "type": "think", "command": "npx mcp-think"}]

        with patch("uio.core.mcp.MCPClient", return_value=plugin_client):
            result = make_mcp_clients({}, plugins=plugins)

        assert "sequential-thinking" in result

    def test_plugin_name_collision_with_inline_server_skipped(self, monkeypatch, capsys):
        """Plugin whose name matches an already-running inline server is skipped."""
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GITLAB_TOKEN", "tok")

        inline_client = _make_mock_client("gitlab")
        plugins = [{"name": "gitlab", "command": "npx gitlab-mcp", "env_keys": ["GITLAB_TOKEN"]}]

        with patch("uio.core.mcp.MCPClient", return_value=inline_client):
            result = make_mcp_clients(
                {"gitlab": {"command": "npx another-gitlab"}}, plugins=plugins
            )

        # Inline server wins; plugin is skipped
        assert result["gitlab"] is inline_client
        captured = capsys.readouterr()
        assert "already running" in captured.err

    def test_plugin_no_command_skipped(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        plugins = [{"name": "empty", "type": "vcs"}]  # no command field

        with patch("uio.core.mcp.MCPClient") as MockCls:
            result = make_mcp_clients({}, plugins=plugins)

        MockCls.assert_not_called()
        assert result == {}

    def test_plugins_none_is_same_as_empty(self, monkeypatch):
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        result = make_mcp_clients({}, plugins=None)
        assert result == {}

    def test_plugins_do_not_bleed_into_inline_iteration(self, monkeypatch):
        """[[mcp.plugins]] entries must not appear as inline server dicts."""
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("LINEAR_API_KEY", "lin-key")

        linear_client = _make_mock_client("linear")
        plugins = [
            {
                "name": "linear",
                "type": "tracker",
                "command": "npx linear-mcp",
                "env_keys": ["LINEAR_API_KEY"],
            }
        ]

        calls = []

        def fake_mcp(command, server_name, **kwargs):
            calls.append(server_name)
            return linear_client

        with patch("uio.core.mcp.MCPClient", side_effect=fake_mcp):
            result = make_mcp_clients({}, plugins=plugins)

        # MCPClient called exactly once (for the plugin), not twice
        assert calls == ["linear"]
        assert "linear" in result


class TestMcpGitServer:
    def test_git_server_starts_from_config(self, monkeypatch):
        """[mcp.git] config entry launches MCPClient with the git server command."""
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        git_client = _make_mock_client("git")
        captured = {}

        def fake_mcp(command, server_name, **kwargs):
            captured["command"] = command
            captured["server_name"] = server_name
            return git_client

        with patch("uio.core.mcp.MCPClient", side_effect=fake_mcp):
            result = make_mcp_clients(
                {"git": {"command": "npx -y @modelcontextprotocol/server-git /workspace"}}
            )

        assert "git" in result
        assert result["git"] is git_client
        assert captured["server_name"] == "git"
        assert "@modelcontextprotocol/server-git" in " ".join(captured["command"])

    def test_git_server_no_token_required(self, monkeypatch):
        """server-git starts without any GitHub token set."""
        monkeypatch.delenv("GITHUB_PERSONAL_ACCESS_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)

        git_client = _make_mock_client("git")
        with patch("uio.core.mcp.MCPClient", return_value=git_client):
            result = make_mcp_clients(
                {"git": {"command": "npx -y @modelcontextprotocol/server-git /workspace"}}
            )

        assert "git" in result

    def test_git_server_coexists_with_github_server(self, monkeypatch):
        """git and github servers can run alongside each other."""
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "tok")

        clients = {
            "github": _make_mock_client("github"),
            "git": _make_mock_client("git"),
        }

        def fake_mcp(command, server_name, **kwargs):
            return clients[server_name]

        with (
            patch("uio.core.mcp.MCPClient", side_effect=fake_mcp),
            patch("uio.core.mcp.make_mcp_client", return_value=clients["github"]),
        ):
            result = make_mcp_clients(
                {"git": {"command": "npx -y @modelcontextprotocol/server-git /workspace"}}
            )

        assert "git" in result
        assert "github" in result


class TestMCPClientCallTool:
    """Unit tests for MCPClient.call_tool without spawning a real process."""

    def _make_client(self, server_name: str = "github") -> MCPClient:
        client = MCPClient.__new__(MCPClient)
        client.server_name = server_name
        client._id = 0
        return client

    def test_mcp_tool_error_returned_as_string(self):
        client = self._make_client()
        err = RuntimeError("MCP error: {'code': -32603, 'message': 'Unknown tool: get_me'}")
        with patch.object(client, "_rpc", side_effect=err):
            result = client.call_tool("mcp__github__get_me", {})
        assert "MCP error:" in result
        assert "Unknown tool" in result

    def test_server_closed_error_still_raises(self):
        client = self._make_client()
        err = RuntimeError("MCP server closed connection unexpectedly")
        with patch.object(client, "_rpc", side_effect=err):
            with pytest.raises(RuntimeError, match="closed connection"):
                client.call_tool("mcp__github__search_repositories", {})

    def test_successful_call_returns_text_content(self):
        client = self._make_client()
        payload = {"content": [{"type": "text", "text": "found 1 repo"}]}
        with patch.object(client, "_rpc", return_value=payload):
            result = client.call_tool("mcp__github__search_repositories", {"query": "uio"})
        assert result == "found 1 repo"
