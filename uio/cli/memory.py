"""uio memory subcommands: list, view, clear."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from uio.config import load_config
from uio.core.memory import estimate_tokens, load_memory_files


@click.group("memory", no_args_is_help=True)
def memory_group() -> None:
    """Manage persistent memory files.

    Memory files live in .uio/memory/*.memory.md and are injected into
    the system prompt at agent/skill startup.
    """


@memory_group.command("list")
def memory_list_cmd() -> None:
    """List all memory files with name, scope, and body size in tokens."""
    cfg = load_config()
    memory_dir = cfg["dirs"]["memory"]
    entries = load_memory_files(memory_dir)
    if not entries:
        click.echo(f"  No memory files found (expected {memory_dir}/*.memory.md).")
        return
    rows = []
    for path, fm, body in entries:
        name = fm.get("name", Path(path).stem)
        scope = fm.get("scope", "project")
        tokens = estimate_tokens(body) if body else 0
        rows.append([name, scope, str(tokens)])
    headers = ["NAME", "SCOPE", "TOKENS"]
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    click.echo("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo("  ".join(cell.ljust(w) for cell, w in zip(row, widths)))


@memory_group.command("view")
@click.argument("name", metavar="NAME")
def memory_view_cmd(name: str) -> None:
    """Print the body of the named memory file.

    NAME is the value of the 'name' frontmatter field.
    """
    cfg = load_config()
    memory_dir = cfg["dirs"]["memory"]
    entries = load_memory_files(memory_dir)
    for path, fm, body in entries:
        if fm.get("name") == name or Path(path).stem == name:
            if not body:
                click.echo(f"  (memory '{name}' is empty)")
                return
            click.echo(body)
            return
    click.echo(f"  Memory '{name}' not found in {memory_dir}.", err=True)
    sys.exit(1)


@memory_group.command("clear")
@click.option(
    "--session",
    is_flag=True,
    default=False,
    help="Clear only session-scoped memory files (default: clear all).",
)
def memory_clear_cmd(session: bool) -> None:
    """Truncate memory file bodies.

    Without --session, clears ALL memory files (project and session).
    With --session, clears only session-scoped memory files.

    \b
    Examples:
      uio memory clear
      uio memory clear --session
    """
    cfg = load_config()
    memory_dir = cfg["dirs"]["memory"]
    entries = load_memory_files(memory_dir)
    if not entries:
        click.echo(f"  No memory files found in {memory_dir}.")
        return

    from uio.core.memory import _write_memory_body

    cleared = 0
    for path, fm, body in entries:
        scope = fm.get("scope", "project")
        if session and scope != "session":
            continue
        if body:
            _write_memory_body(path, fm, "")
            name = fm.get("name", Path(path).stem)
            click.echo(f"  Cleared: {name} ({scope})")
            cleared += 1
    if cleared == 0:
        click.echo("  Nothing to clear.")
    else:
        click.echo(f"\n  {cleared} memory file(s) cleared.")
