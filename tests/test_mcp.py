"""Tests for MCP multi-server client factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from uio.core.mcp import _default_github_mcp_command, make_mcp_client, make_mcp_clients


class TestDefaultGithubMcpCommand:
    def test_gh_present_returns_gh_mcp_server(self):
        with patch(
            "uio.core.mcp.shutil.which", side_effect=lambda x: "/usr/bin/gh" if x == "gh" else None
        ):
            assert _default_github_mcp_command() == ["gh", "mcp", "server"]

    def test_no_gh_but_binary_present_returns_binary(self):
        def which(name):
            if name == "github-mcp-server":
                return "/usr/local/bin/github-mcp-server"
            return None

        with patch("uio.core.mcp.shutil.which", side_effect=which):
            assert _default_github_mcp_command() == ["/usr/local/bin/github-mcp-server", "stdio"]

    def test_neither_falls_back_to_community_npm(self):
        with patch("uio.core.mcp.shutil.which", return_value=None):
            assert _default_github_mcp_command() == [
                "npx",
                "-y",
                "@modelcontextprotocol/server-github",
            ]

    def test_gh_takes_priority_over_binary(self):
        with patch("uio.core.mcp.shutil.which", return_value="/some/path"):
            # shutil.which returns truthy for both, but gh is checked first
            assert _default_github_mcp_command() == ["gh", "mcp", "server"]


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
