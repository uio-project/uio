"""uio workflow subcommands: run, list."""

from __future__ import annotations

import click

from uio.cli._helpers import list_definitions, print_definition_table
from uio.config import load_config
from uio.core.tools import SHELL_CHOICES
from uio.core.workflow import run_workflow


@click.group("workflow", no_args_is_help=True)
def workflow_group() -> None:
    """Run and discover multi-step workflows.

    Workflows are loaded from .uio/workflows/*.workflow.md.
    """


@workflow_group.command("run")
@click.argument("workflow_name", metavar="WORKFLOW")
@click.argument("arg", required=False)
@click.option(
    "--provider",
    default=None,
    help="LLM provider: gemini, openai, or ollama (default: auto-routes).",
)
@click.option("--model", default=None, help="Model name override.")
@click.option("--no-mcp", is_flag=True, default=False, help="Disable all MCP servers.")
@click.option(
    "--shell",
    type=click.Choice(SHELL_CHOICES),
    default=None,
    help="Shell for run_command (default: powershell on Windows, bash/sh on POSIX).",
)
def workflow_run_cmd(
    workflow_name: str,
    arg: str | None,
    provider: str | None,
    model: str | None,
    no_mcp: bool,
    shell: str | None,
) -> None:
    """Run a named workflow sequentially.

    WORKFLOW is the workflow name (stem of the .workflow.md file).
    ARG is an optional positional argument injected as {{ input }} in step args.

    \b
    Examples:
      uio workflow run review-and-fix
      uio workflow run review-and-fix "owner/repo#42"
    """
    cfg = load_config()
    run_workflow(
        workflow_name,
        arg,
        cfg=cfg,
        provider=provider,
        model=model,
        no_mcp=no_mcp,
        shell=shell,
    )


@workflow_group.command("list")
def workflow_list_cmd() -> None:
    """List all available workflows."""
    cfg = load_config()
    workflows_dir = cfg["dirs"]["workflows"]
    defs = list_definitions(f"{workflows_dir}/*.workflow.md")
    if not defs:
        click.echo(f"  No workflows found (expected {workflows_dir}/*.workflow.md).")
        return
    rows = []
    for stem, fm, _ in defs:
        desc = fm.get("description", "—")
        steps = fm.get("steps") or []
        if len(desc) > 64:
            desc = desc[:61] + "..."
        rows.append([stem, str(len(steps)), desc])
    print_definition_table(rows, ["NAME", "STEPS", "DESCRIPTION"])
