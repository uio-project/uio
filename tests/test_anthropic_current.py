"""The Anthropic client on current models: adaptive thinking, prompt caching, a gateway
endpoint, a turn with tools off, and the cost of cached tokens."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from uio.core.clients import (
    PROVIDER_DEFAULTS,
    PROVIDER_SMALL_MODELS,
    AnthropicClient,
    uses_adaptive_thinking,
    with_cache_breakpoint,
)
from uio.core.ledger import estimate_cost_usd, write_cost_ledger
from uio.core.routing import provider_credential, select_provider_chain


@pytest.mark.parametrize(
    ("model", "adaptive"),
    [
        ("claude-opus-5-5", True),
        ("claude-sonnet-5-5", True),
        ("claude-fable-5-2", True),
        ("claude-opus-5", True),
        ("claude-sonnet-4-6", True),
        ("claude-opus-4-7", True),
        ("claude-haiku-4-5-20251001", False),
        ("claude-sonnet-4-5", False),
        ("claude-opus-4-20250514", False),  # a date is not a minor version
        ("claude-opus", True),  # a gateway alias: taken to be current
    ],
)
def test_which_models_take_adaptive_thinking(model, adaptive):
    assert uses_adaptive_thinking(model) is adaptive


def test_the_defaults_are_current_models():
    assert PROVIDER_DEFAULTS["anthropic"] == "claude-sonnet-5-5"
    assert PROVIDER_SMALL_MODELS["anthropic"] == "claude-haiku-5-5"


def make_client(model: str, complexity: str = "large") -> tuple[AnthropicClient, MagicMock]:
    client = AnthropicClient.__new__(AnthropicClient)
    client._model = model
    client._tools = [{"name": "read_file", "description": "d", "input_schema": {"type": "object"}}]
    client._complexity = complexity
    client._max_tokens = 16000
    client._last_raw_content = []
    api = MagicMock()
    usage = SimpleNamespace(
        input_tokens=12,
        output_tokens=7,
        cache_read_input_tokens=900,
        cache_creation_input_tokens=40,
    )
    api.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="done")], usage=usage
    )
    client._client = api
    return client, api


def test_a_current_model_gets_adaptive_thinking_and_an_old_one_a_budget():
    client, api = make_client("claude-opus-5-5")
    client.chat("sys", [{"role": "user", "content": "go"}])
    assert api.messages.create.call_args.kwargs["thinking"] == {"type": "adaptive"}
    client, api = make_client("claude-haiku-4-5-20251001")
    client.chat("sys", [{"role": "user", "content": "go"}])
    assert api.messages.create.call_args.kwargs["thinking"]["type"] == "enabled"
    client, api = make_client("claude-opus-5-5", complexity="small")
    client.chat("sys", [{"role": "user", "content": "go"}])
    assert "thinking" not in api.messages.create.call_args.kwargs


def test_the_system_prompt_and_the_newest_message_carry_cache_breakpoints():
    client, api = make_client("claude-opus-5-5")
    history = [
        {"role": "user", "content": "go"},
        {
            "role": "assistant",
            "content": [{"type": "tool_use", "id": "t1", "name": "read_file", "input": {}}],
        },
        {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "text"}],
        },
    ]
    stored = json.dumps(history)
    client.chat("sys", history)
    kwargs = api.messages.create.call_args.kwargs
    assert kwargs["system"] == [
        {"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}
    ]
    assert kwargs["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in json.dumps(kwargs["messages"][:-1])
    assert json.dumps(history) == stored  # the stored history is never marked


def test_a_breakpoint_on_a_plain_text_message():
    marked = with_cache_breakpoint([{"role": "user", "content": "hello"}])
    assert marked == [
        {
            "role": "user",
            "content": [{"type": "text", "text": "hello", "cache_control": {"type": "ephemeral"}}],
        }
    ]
    assert with_cache_breakpoint([]) == []


def test_a_turn_with_tools_off_says_so_to_the_api():
    client, api = make_client("claude-opus-5-5")
    client.chat("sys", [{"role": "user", "content": "go"}], tools_enabled=False)
    assert api.messages.create.call_args.kwargs["tool_choice"] == {"type": "none"}
    client.chat("sys", [{"role": "user", "content": "go"}])
    assert "tool_choice" not in api.messages.create.call_args.kwargs


def test_cached_tokens_are_reported_apart():
    client, _api = make_client("claude-opus-5-5")
    usage = client.chat("sys", [{"role": "user", "content": "go"}]).usage
    assert (
        usage.prompt_tokens,
        usage.completion_tokens,
        usage.cache_read_tokens,
        usage.cache_write_tokens,
    ) == (12, 7, 900, 40)


def test_the_runner_note_joins_the_last_user_turn():
    client = AnthropicClient.__new__(AnthropicClient)
    history = [
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "x"}]}
    ]
    client.append_user_text(history, "Answer now.")
    assert len(history) == 1 and history[0]["content"][-1] == {
        "type": "text",
        "text": "Answer now.",
    }
    history = [{"role": "assistant", "content": [{"type": "text", "text": "hi"}]}]
    client.append_user_text(history, "Answer now.")
    assert history[-1] == {"role": "user", "content": "Answer now."}


def test_a_base_url_reaches_the_sdk():
    with patch("anthropic.Anthropic") as sdk:
        AnthropicClient(model="claude-opus-5-5", base_url="http://gateway:4000")
        assert sdk.call_args.kwargs == {"base_url": "http://gateway:4000"}
        AnthropicClient(model="claude-opus-5-5")
        assert sdk.call_args.kwargs == {}


# ── routing and cost ──────────────────────────────────────────────────────────


def test_a_bearer_token_makes_anthropic_available(monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert provider_credential("anthropic") is None
    assert "anthropic" not in select_provider_chain(None, "large", ["anthropic"])
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-gateway")
    assert provider_credential("anthropic") == "ANTHROPIC_AUTH_TOKEN"
    assert select_provider_chain(None, "large", ["anthropic"]) == ["anthropic"]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-direct")
    assert provider_credential("anthropic") == "ANTHROPIC_API_KEY"


def test_cached_tokens_are_priced_at_their_own_rates():
    # Opus 5.5: $4 in, $20 out per million; a cache read is a tenth of the input rate, a write 1.25x.
    cost = estimate_cost_usd(
        "anthropic", "claude-opus-5-5", 1_000_000, 100_000, 10_000_000, 200_000
    )
    assert cost == pytest.approx(4.00 + 2.00 + 4.00 + 1.00)
    assert estimate_cost_usd("anthropic", "claude-haiku-5-5", 1_000_000, 0) == pytest.approx(0.10)


def test_the_ledger_records_cached_tokens_only_when_there_were_any(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    write_cost_ledger(
        "a", "anthropic", "claude-opus-5-5", 10, 5, str(ledger), cache_read_tokens=100
    )
    write_cost_ledger("b", "gemini", "gemini-2.5-flash", 10, 5, str(ledger))
    first, second = (json.loads(line) for line in ledger.read_text().splitlines())
    assert first["cache_read_tokens"] == 100 and first["cache_write_tokens"] == 0
    assert "cache_read_tokens" not in second
