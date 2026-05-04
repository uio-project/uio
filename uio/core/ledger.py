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


def estimate_cost_usd(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> float:
    key = f"{provider}/{model}"
    costs = TOKEN_COSTS_PER_1M.get(key) or TOKEN_COSTS_PER_1M.get(provider)
    if costs is None:
        if key not in _warned_unknown_models:
            _warned_unknown_models.add(key)
            _log.warning("[ledger] unknown model '%s' — cost not tracked", key)
        costs = (0.0, 0.0)
    return (prompt_tokens * costs[0] + completion_tokens * costs[1]) / 1_000_000


def write_cost_ledger(
    agent_name: str,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    ledger_path: str = DEFAULT_LEDGER_PATH,
) -> None:
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent": agent_name,
        "provider": provider,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated_cost_usd": round(
            estimate_cost_usd(provider, model, prompt_tokens, completion_tokens), 6
        ),
    }
    try:
        os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as e:
        print(f"  [cost] Warning: could not write cost ledger: {e}", file=sys.stderr)
