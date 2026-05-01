"""Tests for probe_tool_calling()."""

from __future__ import annotations

from unittest.mock import MagicMock

from uio.core.clients import LLMResponse, probe_tool_calling
from uio.core.tools import ToolCall


def _mock_client(tool_calls: list, text: str | None = None) -> MagicMock:
    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "probe"}]
    client.chat.return_value = LLMResponse(text=text, tool_calls=tool_calls)
    return client


def test_probe_returns_true_when_tool_call_present():
    tc = ToolCall(name="run_command", args={"command": "echo probe"}, call_id="probe-1")
    client = _mock_client(tool_calls=[tc])
    assert probe_tool_calling(client) is True


def test_probe_returns_false_when_no_tool_calls():
    client = _mock_client(tool_calls=[], text='{"name": "run_command"}')
    assert probe_tool_calling(client) is False


def test_probe_returns_false_on_exception():
    client = MagicMock()
    client.build_history.return_value = []
    client.chat.side_effect = Exception("connection refused")
    assert probe_tool_calling(client) is False
