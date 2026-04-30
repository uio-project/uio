"""Shared CLI helpers: definition listing and table printing."""

from __future__ import annotations

from glob import glob
from pathlib import Path

import click

from uio.schema.parser import parse_definition_file


def list_definitions(glob_pattern: str) -> list[tuple[str, dict, str]]:
    """Return (stem, frontmatter, body) for each file matching glob_pattern."""
    results = []
    for path in sorted(glob(glob_pattern)):
        stem = Path(path).name.split(".")[0]
        try:
            fm, body = parse_definition_file(path)
        except Exception:
            fm, body = {}, ""
        results.append((stem, fm, body))
    return results


def print_definition_table(rows: list[list[str]], headers: list[str]) -> None:
    if not rows:
        click.echo("  (none found)")
        return
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    click.echo("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))
