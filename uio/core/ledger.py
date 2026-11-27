"""Cost estimation and JSONL append-only ledger."""

from __future__ import annotations

import datetime
import json
import logging
import os
import sys

from uio.core.clients import TOKEN_COSTS_PER_1M

DEFAULT_LEDGER_PATH = "uio_cost.jsonl"

_log = logging.getLogger(__name__)
_warned_unknown_models: set[str] = set()


# Prompt caching, priced from the model's input rate: a read from the cache costs a tenth of it,
# a write to the cache (five-minute lifetime) a quarter more.
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


def estimate_cost_usd(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    key = f"{provider}/{model}"
    costs = TOKEN_COSTS_PER_1M.get(key) or TOKEN_COSTS_PER_1M.get(provider)
    if costs is None:
        if key not in _warned_unknown_models:
            _warned_unknown_models.add(key)
            _log.warning("unknown model '%s' — cost not tracked", key)
        costs = (0.0, 0.0)
    input_rate, output_rate = costs
    return (
        prompt_tokens * input_rate
        + cache_read_tokens * input_rate * CACHE_READ_MULTIPLIER
        + cache_write_tokens * input_rate * CACHE_WRITE_MULTIPLIER
        + completion_tokens * output_rate
    ) / 1_000_000


def write_cost_ledger(
    agent_name: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    ledger_path: str = DEFAULT_LEDGER_PATH,
    workflow: str | None = None,
    workflow_run_id: str | None = None,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> None:
    entry: dict = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent": agent_name,
    }
    if workflow is not None:
        entry["workflow"] = workflow
    if workflow_run_id is not None:
        entry["workflow_run_id"] = workflow_run_id
    entry.update(
        {
            "provider": provider,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "estimated_cost_usd": round(
                estimate_cost_usd(
                    provider,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    cache_read_tokens,
                    cache_write_tokens,
                ),
                6,
            ),
        }
    )
    # Written only when there were any, so a provider without caching leaves the old shape.
    if cache_read_tokens or cache_write_tokens:
        entry["cache_read_tokens"] = cache_read_tokens
        entry["cache_write_tokens"] = cache_write_tokens
    try:
        os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"  [cost] Warning: could not write cost ledger: {e}", file=sys.stderr)
