"""uio agent subcommands: run, list, inspect, new."""

from __future__ import annotations

import textwrap
from pathlib import Path

import click

from uio.cli._helpers import list_definitions, print_definition_table
from uio.config import load_config
from uio.core.routing import infer_complexity
from uio.core.runner import GuardrailError, IdentityError, ProviderExhaustedError, run_agent
from uio.core.tools import SHELL_CHOICES
from uio.schema.parser import parse_definition_file

_AGENT_TEMPLATE = textwrap.dedent("""\
    ---
    name: {name}
    description: One-line description of what this agent does.
    complexity: small
    tools:
      - terminal
      - github
    ---

    # Agent: {name}

    Your task is to …
""")


@click.group("agent", no_args_is_help=True)
def agent_group() -> None:
    """Run and discover AI agents.

    Agents are multi-turn agentic loops loaded from .uio/agents/*.agent.md.
    """


@agent_group.command("run")
@click.argument("agent_name", metavar="AGENT")
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
    help="Task complexity tier (default: inferred from frontmatter or uio.toml).",
)
@click.option("--base-url", default=None, help="Base URL for an OpenAI-compatible endpoint.")
@click.option(
    "--timeout", default=None, show_default=True, type=int, help="Per-command timeout in seconds."
)
@click.option("--no-mcp", is_flag=True, default=False, help="Disable all MCP servers.")
@click.option(
    "--shell",
    type=click.Choice(SHELL_CHOICES),
    default=None,
    help="Shell for run_command (default: powershell on Windows, bash/sh on POSIX).",
)
def agent_run_cmd(
    agent_name: str,
    arg: str | None,
    provider: str | None,
    model: str | None,
    complexity: str | None,
    base_url: str | None,
    timeout: int | None,
    no_mcp: bool,
    shell: str | None,
) -> None:
    """Run a named AI agent.

    AGENT is the agent name (stem of the .agent.md file).
    ARG is an optional positional argument passed to the agent.

    Examples:

    \b
      uio agent run my-agent
      uio agent run my-agent --provider openai
      uio agent run my-agent --complexity large
      uio agent run my-agent --shell pwsh
    """
    cfg = load_config()
    agents_dir = cfg["dirs"]["agents"]
    definition_path = f"{agents_dir}/{agent_name}.agent.md"
    try:
        run_agent(
            agent_name,
            arg,
            provider=provider or cfg["runtime"].get("default_provider"),
            model=model,
            complexity=complexity,
            base_url=base_url,
            timeout=timeout or cfg["runtime"]["timeout"],
            no_mcp=no_mcp,
            mcp_cfg=cfg["mcp"],
            mcp_plugins=cfg.get("mcp_plugins", []),
            definition_path=definition_path,
            ledger_path=cfg["runtime"]["cost_ledger"],
            large_agent_names=cfg["large_agents"]["names"],
            shell_override=shell,
            max_iterations=cfg["runtime"]["max_iterations"],
            max_iterations_large=cfg["runtime"]["max_iterations_large"],
            anthropic_max_tokens=cfg["runtime"]["anthropic_max_tokens"],
            routing_chain=cfg["runtime"].get("routing_chain"),
            memory_dir=cfg["dirs"]["memory"],
            context_max_tokens=cfg["runtime"]["context_max_tokens"],
            attribution_enabled=cfg["attribution"]["enabled"],
        )
    except GuardrailError as exc:
        click.echo(f"Error: guardrail violated — {exc}", err=True)
        raise SystemExit(1)
    except (IdentityError, ValueError, ProviderExhaustedError) as exc:
        click.echo(str(exc), err=True)
        raise SystemExit(1)


@agent_group.command("list")
def agent_list_cmd() -> None:
    """List all available agents."""
    cfg = load_config()
    agents_dir = cfg["dirs"]["agents"]
    defs = list_definitions(f"{agents_dir}/*.agent.md")
    if not defs:
        click.echo(f"  No agents found (expected {agents_dir}/*.agent.md).")
        return
    rows = []
    for stem, fm, _ in defs:
        complexity = infer_complexity(stem, fm, None, cfg["large_agents"]["names"])
        desc = fm.get("description", "—")
        if len(desc) > 68:
            desc = desc[:65] + "..."
        rows.append([stem, complexity, desc])
    print_definition_table(rows, ["NAME", "COMPLEXITY", "DESCRIPTION"])


@agent_group.command("inspect")
@click.argument("agent_name", metavar="AGENT")
def agent_inspect_cmd(agent_name: str) -> None:
    """Show frontmatter and body preview for an agent."""
    cfg = load_config()
    agents_dir = cfg["dirs"]["agents"]
    path = f"{agents_dir}/{agent_name}.agent.md"
    if not Path(path).exists():
        raise click.ClickException(f"agent not found: {path}")
    fm, body = parse_definition_file(path)
    click.echo(f"  Name:        {fm.get('name', agent_name)}")
    click.echo(f"  Description: {fm.get('description', '—')}")
    click.echo(
        f"  Complexity:  {infer_complexity(agent_name, fm, None, cfg['large_agents']['names'])}"
    )
    if fm.get("tools"):
        click.echo(f"  Tools:       {', '.join(fm['tools'])}")
    click.echo()
    lines = body.splitlines()
    for line in lines[:20]:
        click.echo(f"  {line}")
    if len(lines) > 20:
        click.echo(f"  ... ({len(lines) - 20} more lines)")


@agent_group.command("new")
@click.argument("agent_name", metavar="AGENT")
def agent_new_cmd(agent_name: str) -> None:
    """Scaffold a new agent definition file.

    Example:

    \b
      uio agent new my-agent
    """
    cfg = load_config()
    agents_dir = cfg["dirs"]["agents"]
    Path(agents_dir).mkdir(parents=True, exist_ok=True)
    dest = Path(f"{agents_dir}/{agent_name}.agent.md")
    if dest.exists():
        raise click.ClickException(f"already exists: {dest}")
    dest.write_text(_AGENT_TEMPLATE.format(name=agent_name))
    click.echo(f"  Created: {dest}")
