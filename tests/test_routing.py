"""Tests for routing: complexity inference, model selection, provider chain, cost."""

from uio.core.clients import (
    LLMResponse,
    OllamaClient,
    PROVIDER_DEFAULTS,
    PROVIDER_SMALL_MODELS,
    TokenUsage,
)
from uio.core.ledger import estimate_cost_usd
from uio.core.routing import (
    ROUTING_CHAIN,
    infer_complexity,
    select_model,
    select_provider_chain,
)
from uio.core.tools import ToolCall


# ── infer_complexity ───────────────────────────────────────────────────────────


def test_complexity_cli_override_wins():
    assert infer_complexity("my-agent", {"complexity": "small"}, "large") == "large"


def test_complexity_frontmatter_used_when_no_override():
    assert infer_complexity("my-agent", {"complexity": "small"}, None) == "small"


def test_complexity_frontmatter_large():
    assert infer_complexity("scanner", {"complexity": "large"}, None) == "large"


def test_complexity_large_names_list():
    assert infer_complexity("my-heavy-agent", {}, None, large_names=["my-heavy-agent"]) == "large"


def test_complexity_large_names_normalizes_underscores():
    assert infer_complexity("my_heavy_agent", {}, None, large_names=["my-heavy-agent"]) == "large"


def test_complexity_unknown_defaults_small():
    assert infer_complexity("unknown-agent", {}, None) == "small"


def test_complexity_invalid_frontmatter_falls_through():
    assert infer_complexity("my-agent", {"complexity": "medium"}, None) == "small"


def test_complexity_invalid_override_falls_through():
    assert infer_complexity("my-agent", {"complexity": "large"}, "medium") == "large"


def test_complexity_empty_large_names_list():
    assert infer_complexity("gap-analysis", {}, None, large_names=[]) == "small"


def test_complexity_frontmatter_beats_large_names():
    assert (
        infer_complexity("my-agent", {"complexity": "small"}, None, large_names=["my-agent"])
        == "small"
    )


# ── select_model ───────────────────────────────────────────────────────────────


def test_select_model_explicit_override():
    assert select_model("gemini", "large", "my-custom-model") == "my-custom-model"


def test_select_model_large_gemini():
    assert select_model("gemini", "large", None) == PROVIDER_DEFAULTS["gemini"]


def test_select_model_small_gemini():
    assert select_model("gemini", "small", None) == PROVIDER_SMALL_MODELS["gemini"]


def test_select_model_large_openai():
    assert select_model("openai", "large", None) == PROVIDER_DEFAULTS["openai"]


def test_select_model_small_openai():
    assert select_model("openai", "small", None) == PROVIDER_SMALL_MODELS["openai"]


def test_select_model_large_ollama():
    assert select_model("ollama", "large", None) == PROVIDER_DEFAULTS["ollama"]


def test_select_model_small_ollama():
    assert select_model("ollama", "small", None) == PROVIDER_SMALL_MODELS["ollama"]


def test_select_model_env_var_takes_precedence(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "env-model-override")
    assert select_model("gemini", "large", None) == "env-model-override"


def test_select_model_explicit_override_beats_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "env-model")
    assert select_model("gemini", "large", "explicit-model") == "explicit-model"


# ── select_provider_chain ──────────────────────────────────────────────────────


def test_provider_chain_explicit_override(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert select_provider_chain("openai") == ["openai"]


def test_provider_chain_explicit_override_even_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert select_provider_chain("gemini") == ["gemini"]


def test_provider_chain_auto_includes_gemini_when_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    chain = select_provider_chain(None)
    assert "gemini" in chain
    assert chain.index("gemini") == 0


def test_provider_chain_auto_skips_gemini_when_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    chain = select_provider_chain(None)
    assert "gemini" not in chain


def test_provider_chain_always_includes_ollama(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    chain = select_provider_chain(None)
    assert "ollama" in chain


def test_provider_chain_full_when_all_keys_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    chain = select_provider_chain(None)
    assert chain == ROUTING_CHAIN


def test_provider_chain_respects_routing_order(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    monkeypatch.setenv("OPENAI_API_KEY", "o-key")
    chain = select_provider_chain(None)
    assert chain.index("gemini") < chain.index("openai") < chain.index("ollama")


# ── estimate_cost_usd ──────────────────────────────────────────────────────────


def test_cost_estimate_gemini_flash():
    cost = estimate_cost_usd("gemini", "gemini-2.5-flash", 1_000_000, 1_000_000)
    assert abs(cost - 0.75) < 1e-9


def test_cost_estimate_openai_gpt4o():
    cost = estimate_cost_usd("openai", "gpt-4o", 1_000_000, 1_000_000)
    assert abs(cost - 12.50) < 1e-9


def test_cost_estimate_ollama_is_zero():
    cost = estimate_cost_usd("ollama", "qwen2.5-coder:32b", 100_000, 50_000)
    assert cost == 0.0


def test_cost_estimate_zero_tokens():
    assert estimate_cost_usd("gemini", "gemini-2.5-flash", 0, 0) == 0.0


def test_cost_estimate_unknown_model_falls_back_to_provider():
    cost = estimate_cost_usd("ollama", "some-unknown-model", 500_000, 500_000)
    assert cost == 0.0


# ── TokenUsage / LLMResponse ───────────────────────────────────────────────────


def test_llm_response_usage_defaults_to_none():
    r = LLMResponse(text="hi", tool_calls=[])
    assert r.usage is None


def test_llm_response_usage_field():
    usage = TokenUsage(prompt_tokens=100, completion_tokens=50)
    r = LLMResponse(text="hi", tool_calls=[], usage=usage)
    assert r.usage.prompt_tokens == 100
    assert r.usage.completion_tokens == 50


# ── OllamaClient ──────────────────────────────────────────────────────────────


def ollama_client() -> OllamaClient:
    return OllamaClient.__new__(OllamaClient)


def tc(cmd: str = "echo hi", call_id: str = "tc-1") -> ToolCall:
    return ToolCall(name="run_command", args={"command": cmd}, call_id=call_id)


def test_ollama_inherits_openai_append_turn_text_only():
    client = ollama_client()
    history = [{"role": "user", "content": "begin"}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    assert history[1] == {"role": "assistant", "content": "Done.", "tool_calls": None}


def test_ollama_inherits_openai_append_turn_tool_result():

    client = ollama_client()
    history = [{"role": "user", "content": "begin"}]
    call = tc(call_id="tc-1")
    client.append_turn(history, LLMResponse(text=None, tool_calls=[call]), [(call, "output\n")])
    assert len(history) == 3
    assert history[2]["role"] == "tool"
    assert history[2]["tool_call_id"] == "tc-1"


def test_ollama_inherits_build_history():
    client = ollama_client()
    history = client.build_history("hello")
    assert history == [{"role": "user", "content": "hello"}]
