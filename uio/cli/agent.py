"""uio agent subcommands: run, list, inspect, new."""

from __future__ import annotations

import concurrent.futures
import sys
import textwrap
import threading
from pathlib import Path
from typing import NamedTuple

import click

from uio.cli._helpers import list_definitions, print_definition_table
from uio.config import load_config
from uio.core.ledger import estimate_cost_usd
from uio.core.routing import infer_complexity
from uio.core.runner import GuardrailError, IdentityError, ProviderExhaustedError, run_agent
from uio.core.tools import SHELL_CHOICES
from uio.schema.parser import parse_definition_file

_FOREACH_CONCURRENCY_DEFAULT = 4

_print_lock = threading.Lock()


class _ForeachResult(NamedTuple):
    item: str
    success: bool
    prompt_tokens: int
    completion_tokens: int
    provider: str
    model: str
    error: str | None


def _parse_foreach_items(foreach: str) -> list[str]:
    """Return the non-empty lines from *foreach*.

    If *foreach* starts with ``@`` the remainder is treated as a file path and
    the file's contents are read.  Otherwise the string itself is split on
    newlines.  Empty / whitespace-only lines are always discarded.
    """
    if foreach.startswith("@"):
        path = Path(foreach[1:])
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise click.ClickException(f"cannot read --foreach file {path}: {exc}") from exc
    else:
        text = foreach
    return [line.strip() for line in text.splitlines() if line.strip()]


def _run_foreach(
    *,
    items: list[str],
    concurrency: int,
    agent_name: str,
    cfg: dict,
    provider: str | None,
    model: str | None,
    complexity: str | None,
    base_url: str | None,
    timeout: int,
    no_mcp: bool,
    shell: str | None,
) -> None:
    """Fan out *run_agent* across *items* with up to *concurrency* workers.

    Prints a per-item header/footer, then an aggregated cost table at the end.
    Exits with the worst-case exit code (1 if any item failed).
    """
    agents_dir = cfg["dirs"]["agents"]
    definition_path = f"{agents_dir}/{agent_name}.agent.md"

    results: list[_ForeachResult] = []
    results_lock = threading.Lock()

    def _run_one(item: str) -> _ForeachResult:
        # Each worker captures tokens via a thin wrapper that intercepts
        # write_cost_ledger so we can tally per-item costs without parsing
        # the ledger file.
        captured: dict = {"prompt": 0, "completion": 0, "provider": "", "model": ""}

        import uio.core.runner as _runner_mod

        original_write = _runner_mod.write_cost_ledger

        def _capture_write(
            a_name: str,
            p: str,
            m: str,
            prompt_tok: int,
            completion_tok: int,
            ledger_path: str,
        ) -> None:
            captured["prompt"] += prompt_tok
            captured["completion"] += completion_tok
            captured["provider"] = p
            captured["model"] = m
            original_write(a_name, p, m, prompt_tok, completion_tok, ledger_path)

        error: str | None = None
        success = True
        with _print_lock:
            click.echo(f"\n{'=' * 60}")
            click.echo(f"  Item: {item}")
            click.echo(f"{'=' * 60}")

        try:
            import uio.core.runner as _runner_mod2  # noqa: F811 — re-import for clarity

            original2 = _runner_mod2.write_cost_ledger
            _runner_mod2.write_cost_ledger = _capture_write  # type: ignore[assignment]
            try:
                run_agent(
                    agent_name,
                    item,
                    provider=provider or cfg["runtime"].get("default_provider"),
                    model=model,
                    complexity=complexity,
                    base_url=base_url,
                    timeout=timeout,
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
            finally:
                _runner_mod2.write_cost_ledger = original2  # type: ignore[assignment]
        except (GuardrailError, IdentityError, ValueError, ProviderExhaustedError) as exc:
            success = False
            error = str(exc)
            with _print_lock:
                click.echo(f"  [foreach] Error for item {item!r}: {exc}", err=True)
        except Exception as exc:  # noqa: BLE001
            success = False
            error = str(exc)
            with _print_lock:
                click.echo(f"  [foreach] Unexpected error for item {item!r}: {exc}", err=True)

        return _ForeachResult(
            item=item,
            success=success,
            prompt_tokens=captured["prompt"],
            completion_tokens=captured["completion"],
            provider=captured["provider"],
            model=captured["model"],
            error=error,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_run_one, item): item for item in items}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            with results_lock:
                results.append(result)

    # Sort results to match original item order for a stable display.
    item_order = {item: idx for idx, item in enumerate(items)}
    results.sort(key=lambda r: item_order.get(r.item, 0))

    # Aggregated cost summary.
    click.echo(f"\n{'=' * 60}")
    click.echo("  Foreach summary")
    click.echo(f"{'=' * 60}")
    total_cost = 0.0
    total_prompt = 0
    total_completion = 0
    failed_items: list[str] = []
    for r in results:
        status = "OK" if r.success else "FAIL"
        item_cost = (
            estimate_cost_usd(r.provider, r.model, r.prompt_tokens, r.completion_tokens)
            if r.provider
            else 0.0
        )
        total_cost += item_cost
        total_prompt += r.prompt_tokens
        total_completion += r.completion_tokens
        cost_str = f"${item_cost:.6f}" if r.provider else "n/a"
        click.echo(f"  [{status}] {r.item!r:40s}  {cost_str}")
        if not r.success:
            failed_items.append(r.item)
    click.echo(f"{'─' * 60}")
    click.echo(
        f"  Total: {len(results)} items, {len(failed_items)} failed"
        f"  |  tokens: {total_prompt + total_completion:,}"
        f"  |  est. cost: ${total_cost:.6f}"
    )
    click.echo(f"{'=' * 60}")

    if failed_items:
        sys.exit(1)


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
@click.option(
    "--foreach",
    "foreach",
    default=None,
    metavar="ITEMS",
    help=(
        "Run the agent once per item in a newline-delimited list, concurrently. "
        "Pass the list as a string or prefix with '@' to read from a file "
        "(e.g. --foreach @items.txt). Incompatible with ARG."
    ),
)
@click.option(
    "--concurrency",
    default=_FOREACH_CONCURRENCY_DEFAULT,
    show_default=True,
    type=click.IntRange(min=1),
    help="Maximum number of parallel workers when --foreach is used.",
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
    foreach: str | None,
    concurrency: int,
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
      uio agent run my-agent --foreach "$(gh pr list --json number -q '.[].number')"
      uio agent run my-agent --foreach @items.txt --concurrency 8
    """
    cfg = load_config()
    resolved_timeout = timeout or cfg["runtime"]["timeout"]

    if foreach is not None:
        if arg is not None:
            raise click.UsageError("ARG and --foreach are mutually exclusive.")
        items = _parse_foreach_items(foreach)
        if not items:
            click.echo("  [foreach] No items to process.", err=True)
            return
        click.echo(f"  [foreach] {len(items)} item(s), concurrency={concurrency}")
        _run_foreach(
            items=items,
            concurrency=concurrency,
            agent_name=agent_name,
            cfg=cfg,
            provider=provider,
            model=model,
            complexity=complexity,
            base_url=base_url,
            timeout=resolved_timeout,
            no_mcp=no_mcp,
            shell=shell,
        )
        return

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
            timeout=resolved_timeout,
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
