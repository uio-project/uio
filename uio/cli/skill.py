"""uio skill subcommands: run, list, inspect, new."""

from __future__ import annotations

import textwrap
from pathlib import Path

import click

from uio.cli._helpers import list_definitions, print_definition_table
from uio.config import load_config
from uio.core.runner import GuardrailError, IdentityError, ProviderExhaustedError, run_agent
from uio.core.tools import SHELL_CHOICES
from uio.schema.parser import parse_definition_file

_SKILL_TEMPLATE = textwrap.dedent("""\
    ---
    name: {name}
    description: One-line description of what this skill does.
    ---

    # Skill: {name}

    Your task is to …
""")


@click.group("skill", no_args_is_help=True)
def skill_group() -> None:
    """Run and discover reusable skills.

    Skills are loaded from .uio/skills/*.skill.md.
    """


@skill_group.command("run")
@click.argument("skill_name", metavar="SKILL")
@click.argument("arg", required=False)
@click.option(
    "--provider",
    default=None,
    help="LLM provider: gemini, openai, or ollama (default: auto-routes).",
)
@click.option("--model", default=None, help="Model name override.")
@click.option(
    "--complexity",
    type=click.Choice(["large", "small"]),
    default=None,
    help="Task complexity tier.",
)
@click.option("--base-url", default=None, help="Base URL for an OpenAI-compatible endpoint.")
@click.option("--timeout", default=None, type=int, help="Per-command timeout in seconds.")
@click.option("--no-mcp", is_flag=True, default=False, help="Disable all MCP servers.")
@click.option(
    "--shell",
    type=click.Choice(SHELL_CHOICES),
    default=None,
    help="Shell for run_command (default: powershell on Windows, bash/sh on POSIX).",
)
def skill_run_cmd(
    skill_name: str,
    arg: str | None,
    provider: str | None,
    model: str | None,
    complexity: str | None,
    base_url: str | None,
    timeout: int | None,
    no_mcp: bool,
    shell: str | None,
) -> None:
    """Run a named skill as a standalone agent loop.

    SKILL is the skill name (stem of the .skill.md file).
    """
    cfg = load_config()
    skills_dir = cfg["dirs"]["skills"]
    definition_path = f"{skills_dir}/{skill_name}.skill.md"
    try:
        run_agent(
            skill_name,
            arg,
            provider=provider or cfg["runtime"].get("default_provider"),
            model=model,
            complexity=complexity,
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
    except GuardrailError as exc:
        click.echo(f"Error: guardrail violated — {exc}", err=True)
        raise SystemExit(1)
    except (IdentityError, FileNotFoundError, ProviderExhaustedError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1)


@skill_group.command("list")
def skill_list_cmd() -> None:
    """List all available skills."""
    cfg = load_config()
    skills_dir = cfg["dirs"]["skills"]
    defs = list_definitions(f"{skills_dir}/*.skill.md")
    if not defs:
        click.echo(f"  No skills found (expected {skills_dir}/*.skill.md).")
        return
    rows = []
    for stem, fm, _ in defs:
        desc = fm.get("description", "—")
        if len(desc) > 72:
            desc = desc[:69] + "..."
        rows.append([stem, desc])
    print_definition_table(rows, ["NAME", "DESCRIPTION"])


@skill_group.command("inspect")
@click.argument("skill_name", metavar="SKILL")
def skill_inspect_cmd(skill_name: str) -> None:
    """Show frontmatter and body preview for a skill."""
    cfg = load_config()
    skills_dir = cfg["dirs"]["skills"]
    path = f"{skills_dir}/{skill_name}.skill.md"
    if not Path(path).exists():
        raise click.ClickException(f"skill not found: {path}")
    fm, body = parse_definition_file(path)
    click.echo(f"  Name:        {fm.get('name', skill_name)}")
    click.echo(f"  Description: {fm.get('description', '—')}")
    click.echo()
    lines = body.splitlines()
    for line in lines[:20]:
        click.echo(f"  {line}")
    if len(lines) > 20:
        click.echo(f"  ... ({len(lines) - 20} more lines)")


@skill_group.command("new")
@click.argument("skill_name", metavar="SKILL")
def skill_new_cmd(skill_name: str) -> None:
    """Scaffold a new skill definition file."""
    cfg = load_config()
    skills_dir = cfg["dirs"]["skills"]
    Path(skills_dir).mkdir(parents=True, exist_ok=True)
    dest = Path(f"{skills_dir}/{skill_name}.skill.md")
    if dest.exists():
        raise click.ClickException(f"already exists: {dest}")
    dest.write_text(_SKILL_TEMPLATE.format(name=skill_name))
    click.echo(f"  Created: {dest}")
