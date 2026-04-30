"""uio cost — summarise token spend from the cost ledger."""
from __future__ import annotations

import datetime
import json
from pathlib import Path

import click

from uio.config import load_config
from uio.core.ledger import DEFAULT_LEDGER_PATH


def _load_ledger(ledger_path: str, since: str | None, tail: int | None) -> list[dict]:
    p = Path(ledger_path)
    if not p.exists():
        return []
    entries: list[dict] = []
    with p.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if since:
        try:
            cutoff = datetime.datetime.fromisoformat(since)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            raise click.BadParameter(
                f"not a valid ISO 8601 date: {since!r}", param_hint="--since"
            )
        filtered = []
        for e in entries:
            try:
                ts = datetime.datetime.fromisoformat(e.get("timestamp", ""))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
                if ts >= cutoff:
                    filtered.append(e)
            except ValueError:
                filtered.append(e)
        entries = filtered

    if tail is not None:
        entries = entries[-tail:]
    return entries


def _print_cost_table(entries: list[dict]) -> None:
    if not entries:
        click.echo("(no entries in ledger)")
        return
    rows = [
        [
            e.get("timestamp", "")[:19].replace("T", " "),
            e.get("agent", "—"),
            e.get("provider", "—"),
            e.get("model", "—"),
            str(e.get("total_tokens", 0)),
            f"${e.get('estimated_cost_usd', 0.0):.6f}",
        ]
        for e in entries
    ]
    headers = ["TIMESTAMP", "AGENT", "PROVIDER", "MODEL", "TOKENS", "COST"]
    widths = [
        max(len(h), max(len(r[i]) for r in rows))
        for i, h in enumerate(headers)
    ]
    click.echo("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
    total_tokens = sum(e.get("total_tokens", 0) for e in entries)
    total_cost = sum(e.get("estimated_cost_usd", 0.0) for e in entries)
    click.echo()
    click.echo(f"Total: {len(entries)} run(s) | {total_tokens:,} tokens | ${total_cost:.6f}")


@click.command("cost")
@click.option("--tail", default=None, type=int, metavar="N",
              help="Show only the last N entries.")
@click.option("--since", default=None, metavar="DATE",
              help="Show entries on or after DATE (ISO 8601).")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Emit raw JSON lines instead of a formatted table.")
@click.option("--ledger", default=None, metavar="PATH",
              help="Path to the cost ledger file (default: from uio.toml or uio_cost.jsonl).")
def cost_cmd(
    tail: int | None,
    since: str | None,
    as_json: bool,
    ledger: str | None,
) -> None:
    """Summarise AI token spend from the cost ledger.

    Examples:

    \b
      uio cost
      uio cost --tail 20
      uio cost --since 2026-04-01
      uio cost --json | jq '.estimated_cost_usd'
    """
    if ledger is None:
        ledger = load_config()["runtime"]["cost_ledger"]
    entries = _load_ledger(ledger, since, tail)
    if as_json:
        for e in entries:
            click.echo(json.dumps(e))
        return
    _print_cost_table(entries)
