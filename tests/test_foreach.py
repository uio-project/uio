"""Tests for the --foreach / --concurrency flags on `uio agent run`."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from uio.cli.agent import _parse_foreach_items, agent_group
from uio.core.runner import GuardrailError


# ---------------------------------------------------------------------------
# _parse_foreach_items unit tests
# ---------------------------------------------------------------------------


class TestParseForeachItems:
    def test_splits_on_newlines(self):
        result = _parse_foreach_items("1\n2\n3")
        assert result == ["1", "2", "3"]

    def test_discards_blank_lines(self):
        result = _parse_foreach_items("a\n\nb\n  \nc")
        assert result == ["a", "b", "c"]

    def test_strips_whitespace(self):
        result = _parse_foreach_items("  foo  \n  bar  ")
        assert result == ["foo", "bar"]

    def test_empty_string_returns_empty_list(self):
        assert _parse_foreach_items("") == []

    def test_at_file_reads_contents(self, tmp_path):
        f = tmp_path / "items.txt"
        f.write_text("alpha\nbeta\n\ngamma\n")
        with patch("uio.cli.agent.Path.cwd", return_value=tmp_path):
            result = _parse_foreach_items(f"@{f}")
        assert result == ["alpha", "beta", "gamma"]

    def test_at_file_escaping_cwd_raises_usage_error(self, tmp_path):
        """A @file path that resolves outside cwd must be rejected."""
        import click

        outside = tmp_path / "items.txt"
        outside.write_text("x\n")
        # cwd is set to a subdirectory so tmp_path is outside it
        inner = tmp_path / "inner"
        inner.mkdir()
        with patch("uio.cli.agent.Path.cwd", return_value=inner):
            with pytest.raises(click.UsageError, match="escapes the working directory"):
                _parse_foreach_items(f"@{outside}")

    def test_at_file_missing_raises_click_exception(self, tmp_path):
        import click

        missing = tmp_path / "no_such_file.txt"
        with patch("uio.cli.agent.Path.cwd", return_value=tmp_path):
            with pytest.raises(click.ClickException, match="cannot read"):
                _parse_foreach_items(f"@{missing}")


# ---------------------------------------------------------------------------
# CLI integration tests (CliRunner)
# ---------------------------------------------------------------------------


def _make_agent_def(tmp_path: Path) -> Path:
    """Write a minimal agent definition and return its path."""
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    defn = agents_dir / "probe.agent.md"
    defn.write_text("---\nname: probe\ndescription: test agent\ncomplexity: small\n---\nDo it.\n")
    return defn


def _make_cfg(tmp_path: Path) -> dict:
    """Return a minimal config dict pointing at *tmp_path*."""
    agents_dir = str(tmp_path / "agents")
    return {
        "dirs": {"agents": agents_dir, "memory": None},
        "runtime": {
            "default_provider": "gemini",
            "timeout": 30,
            "cost_ledger": str(tmp_path / "ledger.jsonl"),
            "max_iterations": 5,
            "max_iterations_large": 10,
            "anthropic_max_tokens": None,
            "routing_chain": None,
            "context_max_tokens": 8000,
        },
        "mcp": {},
        "mcp_plugins": [],
        "large_agents": {"names": []},
        "attribution": {"enabled": False},
    }


class TestForeachFlag:
    def test_foreach_runs_each_item(self, tmp_path):
        """Each non-empty item in --foreach triggers one run_agent call."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        call_args: list[tuple] = []

        def mock_run_agent(name, arg, **kwargs):
            call_args.append((name, arg))

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent", side_effect=mock_run_agent),
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--foreach", "item1\nitem2\nitem3"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert len(call_args) == 3
        items_seen = {arg for _, arg in call_args}
        assert items_seen == {"item1", "item2", "item3"}

    def test_foreach_empty_list_returns_early(self, tmp_path):
        """When --foreach yields no items the command exits 0 without calling run_agent."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent") as mock_run,
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--foreach", "\n  \n"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        mock_run.assert_not_called()

    def test_foreach_and_arg_are_mutually_exclusive(self, tmp_path):
        """Providing both ARG and --foreach should exit with a UsageError."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        with patch("uio.cli.agent.load_config", return_value=cfg):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "some-arg", "--foreach", "item1"],
            )

        assert result.exit_code != 0
        assert "mutually exclusive" in result.output.lower() or "mutually exclusive" in (
            result.stderr if hasattr(result, "stderr") else ""
        )

    def test_foreach_at_file(self, tmp_path):
        """@file syntax reads items from a file."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        items_file = tmp_path / "items.txt"
        items_file.write_text("x\ny\n")
        runner = CliRunner()

        call_args: list[str] = []

        def mock_run_agent(name, arg, **kwargs):
            call_args.append(arg)

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent", side_effect=mock_run_agent),
            patch("uio.cli.agent.Path.cwd", return_value=tmp_path),
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--foreach", f"@{items_file}"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        assert set(call_args) == {"x", "y"}

    def test_foreach_failure_causes_nonzero_exit(self, tmp_path):
        """If any item fails the exit code is 1."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        def mock_run_agent(name, arg, **kwargs):
            if arg == "bad":
                raise GuardrailError("cost exceeded")

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent", side_effect=mock_run_agent),
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--foreach", "ok\nbad"],
            )

        assert result.exit_code == 1

    def test_foreach_all_succeed_exit_zero(self, tmp_path):
        """All items succeed → exit 0."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent"),
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--foreach", "a\nb\nc"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0

    def test_foreach_summary_printed(self, tmp_path):
        """The cost summary section appears in output."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent"),
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--foreach", "one\ntwo"],
                catch_exceptions=False,
            )

        assert "Foreach summary" in result.output
        assert "Total:" in result.output

    def test_concurrency_default_is_four(self, tmp_path):
        """--concurrency defaults to 4 (the constant _FOREACH_CONCURRENCY_DEFAULT)."""
        from uio.cli.agent import _FOREACH_CONCURRENCY_DEFAULT

        assert _FOREACH_CONCURRENCY_DEFAULT == 4

    def test_concurrency_option_accepted(self, tmp_path):
        """--concurrency N is accepted without error."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent"),
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--foreach", "a\nb", "--concurrency", "2"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0

    def test_without_foreach_behaves_normally(self, tmp_path):
        """Without --foreach the command calls run_agent exactly once with ARG=None."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        with (
            patch("uio.cli.agent.load_config", return_value=cfg),
            patch("uio.cli.agent.run_agent") as mock_run,
        ):
            result = runner.invoke(
                agent_group,
                ["run", "probe"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0
        mock_run.assert_called_once()
        _, call_kwargs = mock_run.call_args
        # positional: (agent_name, arg, ...)
        assert mock_run.call_args.args[1] is None

    def test_concurrency_without_foreach_raises_usage_error(self, tmp_path):
        """Passing --concurrency without --foreach should produce a UsageError."""
        _make_agent_def(tmp_path)
        cfg = _make_cfg(tmp_path)
        runner = CliRunner()

        with patch("uio.cli.agent.load_config", return_value=cfg):
            result = runner.invoke(
                agent_group,
                ["run", "probe", "--concurrency", "8"],
            )

        assert result.exit_code != 0
        assert "--concurrency requires --foreach" in result.output
