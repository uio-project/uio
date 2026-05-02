"""Tests for per-definition guardrails (max_cost_usd, max_turns, deny_tools)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from uio.core.clients import LLMResponse
from uio.core.runner import GuardrailError, run_agent
from uio.core.tools import ToolCall


def _make_run_args(tmp_path, frontmatter_extra: str = ""):
    defn = tmp_path / "test.agent.md"
    defn.write_text(
        f"---\nname: test-agent\ncomplexity: small\n{frontmatter_extra}---\nDo the task.\n"
    )
    return {
        "agent_name": "test-agent",
        "definition_path": str(defn),
        "no_mcp": True,
        "ledger_path": str(tmp_path / "ledger.jsonl"),
    }


def _always_tool_client(tool_name: str = "run_command"):
    tc = ToolCall(name=tool_name, args={"command": "echo x"}, call_id="t1")
    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]
    client.chat.return_value = LLMResponse(text=None, tool_calls=[tc])
    client.usage = None
    return client


def _terminal_client():
    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]
    client.chat.return_value = LLMResponse(text="Done.", tool_calls=[])
    client.usage = None
    return client


class TestMaxTurns:
    def test_max_turns_from_frontmatter_overrides_global(self, tmp_path):
        """max_turns: 2 in frontmatter stops the loop at 2 even when global cap is 10."""
        client = _always_tool_client()
        fm = "guardrails:\n  max_turns: 2\n"
        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool", return_value="ok"),
        ):
            run_agent(**_make_run_args(tmp_path, fm), max_iterations=10, max_iterations_large=25)

        assert client.chat.call_count == 2

    def test_max_turns_overrides_large_cap(self, tmp_path):
        """max_turns: 3 overrides the large complexity cap."""
        defn = tmp_path / "large.agent.md"
        defn.write_text(
            "---\nname: test-agent\ncomplexity: large\nguardrails:\n  max_turns: 3\n---\nDo the task.\n"
        )
        client = _always_tool_client()
        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool", return_value="ok"),
        ):
            run_agent(
                agent_name="test-agent",
                definition_path=str(defn),
                no_mcp=True,
                ledger_path=str(tmp_path / "ledger.jsonl"),
                max_iterations=10,
                max_iterations_large=25,
            )

        assert client.chat.call_count == 3


class TestMaxCostUsd:
    def test_max_cost_exceeded_raises_guardrail_error(self, tmp_path):
        """When estimated cost exceeds max_cost_usd, GuardrailError is raised."""
        fm = "guardrails:\n  max_cost_usd: 0.000001\n"
        client = MagicMock()
        client.build_history.return_value = [{"role": "user", "content": "begin"}]
        client.chat.return_value = LLMResponse(text="Done.", tool_calls=[])
        # Return non-zero token usage so the cost estimate is positive.
        from uio.core.clients import TokenUsage

        client.chat.return_value = LLMResponse(
            text="Done.",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=10000, completion_tokens=5000),
        )
        client.usage = None

        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch(
                "uio.core.runner.estimate_cost_usd",
                return_value=0.05,  # always over the 0.000001 limit
            ),
        ):
            with pytest.raises(GuardrailError, match="max_cost_usd"):
                run_agent(**_make_run_args(tmp_path, fm))

    def test_no_guardrail_when_cost_under_limit(self, tmp_path):
        """No error when running cost is below max_cost_usd."""
        fm = "guardrails:\n  max_cost_usd: 100.0\n"
        client = _terminal_client()

        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.estimate_cost_usd", return_value=0.001),
        ):
            run_agent(**_make_run_args(tmp_path, fm))  # should not raise


class TestDenyTools:
    def test_deny_tools_exact_match_blocks_tool(self, tmp_path):
        """A tool matching a deny_tools glob is blocked and returns a denial message."""
        fm = "guardrails:\n  deny_tools:\n    - run_command\n"
        tc = ToolCall(name="run_command", args={"command": "echo x"}, call_id="t1")
        client = MagicMock()
        client.build_history.return_value = [{"role": "user", "content": "begin"}]
        # First call returns the tool; second returns terminal.
        client.chat.side_effect = [
            LLMResponse(text=None, tool_calls=[tc]),
            LLMResponse(text="Done.", tool_calls=[]),
        ]
        client.usage = None

        captured_results = []

        def capture_append(history, response, results):
            captured_results.extend(results)

        client.append_turn.side_effect = capture_append

        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool") as mock_execute,
        ):
            run_agent(**_make_run_args(tmp_path, fm))

        # execute_tool must NOT have been called — denial happens before execution.
        mock_execute.assert_not_called()
        assert len(captured_results) == 1
        _, result = captured_results[0]
        assert "denied by guardrail" in result

    def test_deny_tools_glob_blocks_matching_tool(self, tmp_path):
        """A glob pattern in deny_tools blocks matching tool names."""
        fm = "guardrails:\n  deny_tools:\n    - mcp__*__delete_*\n"
        tc = ToolCall(name="mcp__filesystem__delete_file", args={}, call_id="t1")
        client = MagicMock()
        client.build_history.return_value = [{"role": "user", "content": "begin"}]
        client.chat.side_effect = [
            LLMResponse(text=None, tool_calls=[tc]),
            LLMResponse(text="Done.", tool_calls=[]),
        ]
        client.usage = None
        client.append_turn.return_value = None

        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool") as mock_execute,
        ):
            run_agent(**_make_run_args(tmp_path, fm))

        mock_execute.assert_not_called()

    def test_deny_tools_does_not_block_non_matching_tool(self, tmp_path):
        """Tools that do not match deny_tools globs are executed normally."""
        fm = "guardrails:\n  deny_tools:\n    - mcp__*__delete_*\n"
        tc = ToolCall(name="run_command", args={"command": "echo x"}, call_id="t1")
        client = MagicMock()
        client.build_history.return_value = [{"role": "user", "content": "begin"}]
        client.chat.side_effect = [
            LLMResponse(text=None, tool_calls=[tc]),
            LLMResponse(text="Done.", tool_calls=[]),
        ]
        client.usage = None
        client.append_turn.return_value = None

        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool", return_value="ok") as mock_execute,
        ):
            run_agent(**_make_run_args(tmp_path, fm))

        mock_execute.assert_called_once()


class TestGuardrailErrorPropagation:
    def test_guardrail_error_not_swallowed_by_provider_loop(self, tmp_path):
        """GuardrailError propagates out of run_agent, not swallowed by the provider loop."""
        fm = "guardrails:\n  max_cost_usd: 0.000001\n"
        client = _terminal_client()

        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini", "openai"]),
            patch("uio.core.runner.estimate_cost_usd", return_value=1.0),
        ):
            with pytest.raises(GuardrailError):
                run_agent(**_make_run_args(tmp_path, fm))
