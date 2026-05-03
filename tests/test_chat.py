"""Tests for chat module token accumulation in _inner_tool_loop."""

from unittest.mock import MagicMock, patch

from uio.cli.chat import _inner_tool_loop
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
