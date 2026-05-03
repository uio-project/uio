"""Tests for chat module token accumulation in _inner_tool_loop."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from uio.cli.chat import _inner_tool_loop, chat_cmd
from uio.core.clients import LLMResponse, TokenUsage
from uio.core.tools import ToolCall


def _resp(text=None, tool_calls=None, prompt=0, completion=0):
    return LLMResponse(
        text=text,
        tool_calls=tool_calls or [],
        usage=TokenUsage(prompt_tokens=prompt, completion_tokens=completion),
    )


def test_inner_tool_loop_includes_final_response_usage_in_totals():
    """ep/ec must include the final response's usage so callers must not add it again."""
    tool_call = ToolCall(name="run_command", args={"command": "echo hi"}, call_id="tc-1")
    initial = _resp(tool_calls=[tool_call], prompt=10, completion=5)
    final = _resp(text="done", prompt=20, completion=8)

    client = MagicMock()
    history = [{"role": "user", "content": "hi"}]

    with (
        patch("uio.cli.chat._stream_turn", return_value=final),
        patch("uio.cli.chat.execute_tool", return_value="output"),
        patch("uio.cli.chat._approval_gate", return_value=True),
        patch("uio.cli.chat.click"),
    ):
        response, ep, ec = _inner_tool_loop(
            client,
            history,
            "system",
            initial,
            auto_approve=True,
            allow_globs=(),
            deny_globs=(),
            timeout=60,
        )

    assert response is final
    assert ep == 20
    assert ec == 8


def test_inner_tool_loop_accumulates_multiple_inner_turns():
    """ep/ec sums usage across all inner turns when there are multiple tool round-trips."""
    tool_call = ToolCall(name="run_command", args={"command": "echo hi"}, call_id="tc-1")
    initial = _resp(tool_calls=[tool_call], prompt=10, completion=5)
    intermediate = _resp(tool_calls=[tool_call], prompt=15, completion=6)
    final = _resp(text="done", prompt=20, completion=8)

    client = MagicMock()
    history = [{"role": "user", "content": "hi"}]

    with (
        patch("uio.cli.chat._stream_turn", side_effect=[intermediate, final]),
        patch("uio.cli.chat.execute_tool", return_value="output"),
        patch("uio.cli.chat._approval_gate", return_value=True),
        patch("uio.cli.chat.click"),
    ):
        response, ep, ec = _inner_tool_loop(
            client,
            history,
            "system",
            initial,
            auto_approve=True,
            allow_globs=(),
            deny_globs=(),
            timeout=60,
        )

    assert response is final
    assert ep == 15 + 20
    assert ec == 6 + 8


def test_inner_tool_loop_none_usage_does_not_raise_and_leaves_totals_zero():
    """The usage=None guard at line 227 of chat.py must not raise and must leave ep/ec at 0."""
    tool_call = ToolCall(name="run_command", args={"command": "echo hi"}, call_id="tc-1")
    initial = _resp(tool_calls=[tool_call])
    final = LLMResponse(text="done", tool_calls=[], usage=None)

    client = MagicMock()
    history = [{"role": "user", "content": "hi"}]

    with (
        patch("uio.cli.chat._stream_turn", return_value=final),
        patch("uio.cli.chat.execute_tool", return_value="output"),
        patch("uio.cli.chat._approval_gate", return_value=True),
        patch("uio.cli.chat.click"),
    ):
        response, ep, ec = _inner_tool_loop(
            client,
            history,
            "system",
            initial,
            auto_approve=True,
            allow_globs=(),
            deny_globs=(),
            timeout=60,
        )

    assert response is final
    assert ep == 0
    assert ec == 0


def test_chat_cmd_accumulation_no_double_count():
    """total_prompt/completion must equal initial_usage + ep/ec, not + final_usage again."""
    tool_call = ToolCall(name="run_command", args={"command": "ls"}, call_id="tc-1")
    initial_response = LLMResponse(
        text=None,
        tool_calls=[tool_call],
        usage=TokenUsage(prompt_tokens=10, completion_tokens=5),
    )
    final_response = LLMResponse(
        text="done",
        tool_calls=[],
        usage=TokenUsage(prompt_tokens=20, completion_tokens=8),
    )
    ep, ec = 20, 8  # final_response's usage is already inside ep/ec

    captured: dict = {}

    def fake_show_cost(provider, model, p, c):
        captured["prompt"] = p
        captured["completion"] = c

    runner = CliRunner()
    with (
        patch(
            "uio.cli.chat.load_config",
            return_value={
                "runtime": {"timeout": 60, "cost_ledger": None, "default_provider": None}
            },
        ),
        patch("uio.cli.chat.select_provider_chain", return_value=["ollama"]),
        patch("uio.cli.chat.select_model", return_value="test-model"),
        patch("uio.cli.chat.make_client", return_value=MagicMock()),
        patch("builtins.input", side_effect=["hello", EOFError()]),
        patch("uio.cli.chat._stream_turn", return_value=initial_response),
        patch("uio.cli.chat._inner_tool_loop", return_value=(final_response, ep, ec)),
        patch("uio.cli.chat._show_session_cost", side_effect=fake_show_cost),
        patch("uio.cli.chat.write_cost_ledger"),
    ):
        runner.invoke(chat_cmd, ["--tools"])

    # Must be initial (10/5) + loop ep/ec (20/8) = 30/13, not 50/21 (double-counted)
    assert captured.get("prompt") == 30
    assert captured.get("completion") == 13
