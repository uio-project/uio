# Cost Ledger

## Overview

After every `agent run`, `skill run`, `prompt run`, and `chat` session, uio appends a JSON line to `uio_cost.jsonl`. This file is the cost ledger — an append-only record of every LLM call with token counts and estimated spend.

The ledger is append-only by design: it is safe to `tail -f`, survives partial runs, and can never be corrupted by concurrent writes from different processes.

---

## Setup

`uio init` automatically adds `uio_cost.jsonl` to your `.gitignore`. If you created `.uio/` manually, add it yourself:

```bash
echo "uio_cost.jsonl" >> .gitignore
```

Committing the ledger leaks your token spend to collaborators and can cause noisy diffs.

---

## Ledger entry schema

Each line is a JSON object:

```json
{
  "timestamp": "2026-04-30T12:01:05.341000+00:00",
  "agent": "summarise",
  "provider": "gemini",
  "model": "gemini-2.5-flash-lite",
  "prompt_tokens": 512,
  "completion_tokens": 87,
  "total_tokens": 599,
  "estimated_cost_usd": 0.000065
}
```

| Field | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 string (UTC) | When the run completed |
| `agent` | string | Definition name; `"chat"` for REPL sessions |
| `provider` | string | Provider used: `gemini`, `openai`, or `ollama` |
| `model` | string | Exact model string sent to the provider |
| `prompt_tokens` | integer | Input tokens |
| `completion_tokens` | integer | Output tokens |
| `total_tokens` | integer | `prompt_tokens + completion_tokens` |
| `estimated_cost_usd` | float | Estimated cost in USD, rounded to 6 decimal places |

---

## Cost formula

```
estimated_cost_usd = (prompt_tokens × input_rate + completion_tokens × output_rate) / 1_000_000
```

Rates come from `TOKEN_COSTS_PER_1M` in `uio/core/clients.py` (see [Providers — token cost table](07-providers.md#token-cost-reference)). Ollama runs always record `0.0`.

When a `--model` override is used with a model not in the table, the provider-level rate is used as a fallback. If no provider-level rate exists, `0.0` is recorded. The estimates are informational — check your provider's billing dashboard for authoritative numbers.

---

## `uio cost` command

```bash
# All entries, formatted table
uio cost

# Last 20 entries
uio cost --tail 20

# Entries since a date
uio cost --since 2026-04-01

# Entries since a specific time
uio cost --since "2026-04-30T10:00:00"

# Raw JSON lines (one per entry)
uio cost --json

# Different ledger file
uio cost --ledger /path/to/other.jsonl
```

Example table output:

```
TIMESTAMP            AGENT        PROVIDER  MODEL                   TOKENS  COST
2026-04-30 12:01:05  summarise    gemini    gemini-2.5-flash-lite      599  $0.000065
2026-04-30 12:02:14  shell-helper gemini    gemini-2.5-flash-lite     1243  $0.000124
2026-04-30 12:15:33  chat         gemini    gemini-2.5-flash-lite     4218  $0.000422

Total: 3 run(s) | 6,060 tokens | $0.000611
```

---

## `jq` recipes

`uio cost --json` emits one JSON object per line, making it easy to pipe into `jq`.

**Total spend across all runs:**

```bash
uio cost --json | jq -s '[.[].estimated_cost_usd] | add'
```

**Spend grouped by agent:**

```bash
uio cost --json | jq -s '
  group_by(.agent)
  | map({agent: .[0].agent, runs: length, cost: ([.[].estimated_cost_usd] | add)})
  | sort_by(.cost) | reverse
'
```

**Most expensive single run:**

```bash
uio cost --json | jq -s 'max_by(.estimated_cost_usd)'
```

**Total tokens this week:**

```bash
uio cost --since "$(date -d '7 days ago' --iso-8601)" --json \
  | jq -s '[.[].total_tokens] | add'
```

**Runs that cost more than $0.01:**

```bash
uio cost --json | jq 'select(.estimated_cost_usd > 0.01)'
```

**Average cost per run by provider:**

```bash
uio cost --json | jq -s '
  group_by(.provider)
  | map({
      provider: .[0].provider,
      avg_cost: ([.[].estimated_cost_usd] | add / length)
    })
'
```

---

## Custom ledger path

Change the ledger path for a project in `uio.toml`:

```toml
[runtime]
cost_ledger = "logs/uio_cost.jsonl"
```

Or per-invocation with `--ledger`:

```bash
uio cost --ledger /var/log/uio/costs.jsonl
```

This is useful for shared infrastructure where multiple projects or users write to a central ledger.

---

## Write failure handling

If uio cannot write to the ledger (e.g., the directory does not exist or permissions are wrong), it prints a warning to stderr and continues. The run result is not affected by ledger write failures:

```
  [cost] Warning: could not write cost ledger: [Errno 13] Permission denied: 'uio_cost.jsonl'
```

Fix: ensure the directory exists and is writable, or change `cost_ledger` in `uio.toml`.
