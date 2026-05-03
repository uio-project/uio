"""uio prompt subcommands: run, list, new."""

from __future__ import annotations

import textwrap
from pathlib import Path

import click

from uio.cli._helpers import list_definitions, print_definition_table
from uio.config import load_config
from uio.core.runner import run_agent
from uio.core.tools import SHELL_CHOICES

_PROMPT_TEMPLATE = textwrap.dedent("""\
    ---
    name: {name}
    description: One-line description of what this prompt does.
    argument-hint: "[optional-arg]"
    invokable: true
    ---

    Your task is to …
""")


@click.group("prompt", no_args_is_help=True)
def prompt_group() -> None:
    """Run and discover project prompts.

    Prompts are loaded from .uio/prompts/*.prompt.md.
    """


@prompt_group.command("run")
@click.argument("prompt_name", metavar="PROMPT")
@click.argument("arg", required=False)
@click.option(
    "--provider",
    default=None,
    help="LLM provider: gemini, openai, or ollama (default: auto-routes).",
)
@click.option("--model", default=None, help="Model name override.")
@click.option("--base-url", default=None, help="Base URL for an OpenAI-compatible endpoint.")
@click.option("--timeout", default=None, type=int, help="Per-command timeout in seconds.")
@click.option("--no-mcp", is_flag=True, default=False, help="Disable all MCP servers.")
@click.option(
    "--shell",
    type=click.Choice(SHELL_CHOICES),
    default=None,
    help="Shell for run_command (default: powershell on Windows, bash/sh on POSIX).",
)
def prompt_run_cmd(
    prompt_name: str,
    arg: str | None,
    provider: str | None,
    model: str | None,
    base_url: str | None,
    timeout: int | None,
    no_mcp: bool,
    shell: str | None,
) -> None:
    """Run a named prompt.

    PROMPT is the prompt name (stem of the .prompt.md file).
    ARG is an optional positional argument.
    """
    cfg = load_config()
    prompts_dir = cfg["dirs"]["prompts"]
    definition_path = f"{prompts_dir}/{prompt_name}.prompt.md"
    run_agent(
        prompt_name,
        arg,
        provider=provider or cfg["runtime"].get("default_provider"),
        model=model,
        base_url=base_url,
        timeout=timeout or cfg["runtime"]["timeout"],
        no_mcp=no_mcp,
        mcp_cfg=cfg["mcp"],
        mcp_plugins=cfg["mcp_plugins"],
        definition_path=definition_path,
        ledger_path=cfg["runtime"]["cost_ledger"],
        large_agent_names=cfg["large_agents"]["names"],
        shell_override=shell,
        routing_chain=cfg["runtime"].get("routing_chain"),
        memory_dir=cfg["dirs"]["memory"],
        context_max_tokens=cfg["runtime"]["context_max_tokens"],
    )


@prompt_group.command("list")
def prompt_list_cmd() -> None:
    """List all available prompts."""
    cfg = load_config()
    prompts_dir = cfg["dirs"]["prompts"]
    defs = list_definitions(f"{prompts_dir}/*.prompt.md")
    if not defs:
        click.echo(f"  No prompts found (expected {prompts_dir}/*.prompt.md).")
        return
    rows = []
    for stem, fm, _ in defs:
        raw_hint = fm.get("argument-hint", "")
        if isinstance(raw_hint, list):
            hint = " ".join(str(h) for h in raw_hint) or "—"
        else:
            hint = str(raw_hint).strip('"') or "—"
        desc = fm.get("description", "—")
        if len(desc) > 56:
            desc = desc[:53] + "..."
        rows.append([stem, hint, desc])
    print_definition_table(rows, ["NAME", "ARGUMENT", "DESCRIPTION"])


@prompt_group.command("new")
@click.argument("prompt_name", metavar="PROMPT")
def prompt_new_cmd(prompt_name: str) -> None:
    """Scaffold a new prompt definition file."""
    cfg = load_config()
    prompts_dir = cfg["dirs"]["prompts"]
    Path(prompts_dir).mkdir(parents=True, exist_ok=True)
    dest = Path(f"{prompts_dir}/{prompt_name}.prompt.md")
    if dest.exists():
        raise click.ClickException(f"already exists: {dest}")
    dest.write_text(_PROMPT_TEMPLATE.format(name=prompt_name))
    click.echo(f"  Created: {dest}")
