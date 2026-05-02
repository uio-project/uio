"""Provider routing and model-tier selection."""

from __future__ import annotations

import os

from uio.core.clients import PROVIDER_DEFAULTS, PROVIDER_SMALL_MODELS

ROUTING_CHAIN = ["ollama", "openai", "gemini", "anthropic"]

PROVIDER_KEY_ENV: dict[str, str | None] = {
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "ollama": None,
}


def infer_complexity(
    agent_name: str,
    frontmatter: dict,
    override: str | None,
    large_names: list[str] | None = None,
) -> str:
    """Return 'large' or 'small'. Priority: CLI flag > frontmatter > uio.toml list > default."""
    if override in ("large", "small"):
        return override
    fm = frontmatter.get("complexity", "").lower()
    if fm in ("large", "small"):
        return fm
    if large_names:
        normalized = agent_name.lower().replace("_", "-")
        if normalized in [n.lower().replace("_", "-") for n in large_names]:
            return "large"
    return "small"


def select_model(provider: str, complexity: str, model_override: str | None) -> str:
    """Return the model to use, respecting explicit overrides."""
    if model_override:
        return model_override
    env_model = os.environ.get("LLM_MODEL")
    if env_model:
        return env_model
    if complexity == "small":
        return PROVIDER_SMALL_MODELS.get(provider, PROVIDER_DEFAULTS.get(provider, ""))
    return PROVIDER_DEFAULTS.get(provider, "")


def select_provider_chain(
    provider_override: str | None,
    complexity: str = "small",
    routing_chain: list[str] | None = None,
) -> list[str]:
    """Return ordered providers to try.

    If --provider is set, returns that single provider. Otherwise returns all
    providers in the active chain that have their required API key available.
    The active chain is ``routing_chain`` when provided, else ``ROUTING_CHAIN``.

    Ollama is excluded from auto-routing for large-complexity runs because
    local models are unlikely to reliably execute multi-step tool-call chains.
    --provider ollama forces Ollama regardless of complexity.
    """
    if provider_override:
        return [provider_override]
    chain = routing_chain if routing_chain is not None else ROUTING_CHAIN
    available = []
    for p in chain:
        if p == "ollama" and complexity == "large":
            continue
        if p not in PROVIDER_KEY_ENV:
            continue
        key_env = PROVIDER_KEY_ENV[p]
        if key_env is None or os.environ.get(key_env):
            available.append(p)
    # For small complexity, always fall back to Ollama if nothing else is available.
    # For large complexity, Ollama is excluded — an empty list tells the runner to exit cleanly.
    if not available and complexity != "large":
        return ["ollama"]
    return available
