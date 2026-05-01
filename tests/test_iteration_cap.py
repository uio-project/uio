"""Tests for per-complexity MAX_ITERATIONS caps."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from uio.core.clients import LLMResponse
from uio.core.runner import _DEFAULT_MAX_ITERATIONS, _DEFAULT_MAX_ITERATIONS_LARGE, run_agent
from uio.core.tools import ToolCall


def _make_run_args(tmp_path, complexity: str = "small"):
    defn = tmp_path / "test.agent.md"
    defn.write_text(f"---\nname: test-agent\ncomplexity: {complexity}\n---\nDo the task.\n")
    return {
        "agent_name": "test-agent",
        "definition_path": str(defn),
        "no_mcp": True,
        "ledger_path": str(tmp_path / "ledger.jsonl"),
    }


def _always_tool_client():
    """Client that always returns a tool call, forcing the runner to hit the cap."""
    tc = ToolCall(name="run_command", args={"command": "echo x"}, call_id="t1")
    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]
    client.chat.return_value = LLMResponse(text=None, tool_calls=[tc])
    client.usage = None
    return client


class TestDefaultCaps:
    def test_default_small_cap(self):
        assert _DEFAULT_MAX_ITERATIONS == 10

    def test_default_large_cap(self):
        assert _DEFAULT_MAX_ITERATIONS_LARGE == 25


class TestIterationCapPerComplexity:
    def test_small_agent_stops_at_small_cap(self, tmp_path):
        client = _always_tool_client()
        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool", return_value="ok"),
        ):
            run_agent(
                **_make_run_args(tmp_path, "small"), max_iterations=3, max_iterations_large=99
            )

        assert client.chat.call_count == 3

    def test_large_agent_uses_large_cap(self, tmp_path):
        client = _always_tool_client()
        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool", return_value="ok"),
        ):
            run_agent(**_make_run_args(tmp_path, "large"), max_iterations=3, max_iterations_large=5)

        assert client.chat.call_count == 5

    def test_small_agent_does_not_use_large_cap(self, tmp_path):
        client = _always_tool_client()
        with (
            patch("uio.core.runner.make_client", return_value=client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.execute_tool", return_value="ok"),
        ):
            run_agent(
                **_make_run_args(tmp_path, "small"), max_iterations=2, max_iterations_large=99
            )

        assert client.chat.call_count == 2
