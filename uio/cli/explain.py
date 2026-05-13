"""uio explain subcommands: agent, skill, prompt.

Renders the complete system prompt that would be sent to the provider for a
given agent, skill, or prompt definition, annotated with section markers.
Use --raw to strip the markers for copy/paste into an external playground.
"""

from __future__ import annotations

import os
from pathlib import Path

import click

from uio.config import load_config
from uio.core.attribution import build_attribution_instructions
from uio.core.identities import KNOWN_ROLES
from uio.core.memory import build_memory_section
from uio.core.runner import _build_context_section, _build_preamble
from uio.schema.parser import parse_definition_file

# Marker strings used to annotate each section.
_MARKER_PREAMBLE = "--- preamble ---"
_MARKER_BODY = "--- body ---"
_MARKER_CONTEXT = "--- context ---"
_MARKER_ATTRIBUTION = "--- attribution ---"
_MARKER_MEMORY = "--- memory ---"


def _section(marker: str, content: str, raw: bool) -> str:
    """Wrap *content* with *marker* delimiters unless *raw* is True."""
    if raw:
        return content
    return f"{marker}\n{content}\n"


def _explain_definition(
    kind: str,
    name: str,
    definition_path: str,
    raw: bool,
    cfg: dict,
) -> None:
    """Render the assembled system prompt for *definition_path* to stdout."""
    if not Path(definition_path).exists():
        raise click.ClickException(f"{kind} not found: {definition_path}")

    frontmatter, body = parse_definition_file(definition_path)

    # --- preamble ---
    # Use has_mcp=True so the preamble shows the full MCP-available variant,
    # which is the common case.  Users who want to see the no-MCP preamble can
    # inspect the source; explain is a debugging aid, not a perfect replay.
    #
    # Mirror runner.py logic: inject the VCS alias table when vcs-identity is
    # set OR when capabilities includes "vcs".
    role = frontmatter.get("vcs-identity") or frontmatter.get("github-identity")
    _caps = frontmatter.get("capabilities") or []
    if isinstance(_caps, str):
        _caps = [_caps]
    vcs_provider: str | None = None
    if role in KNOWN_ROLES or "vcs" in _caps:
        vcs_provider = frontmatter.get("vcs-provider", "github")
    preamble = _build_preamble(has_mcp=True, vcs_provider=vcs_provider)

    # --- attribution (only for vcs-identity agents) ---
    attribution_block = ""
    if role and role in KNOWN_ROLES and cfg["attribution"]["enabled"]:
        attribution_block = build_attribution_instructions(
            role,
            frontmatter.get("name", name),
            version="<version>",
            vcs_provider=frontmatter.get("vcs-provider", "github"),
            model="<model>",
        )

    # --- context files ---
    context_globs = frontmatter.get("context") or []
    if isinstance(context_globs, str):
        context_globs = [context_globs]

    # Delegate to runner._build_context_section so the output matches exactly
    # what the model sees at runtime (## Context header + ### rel_path headings).
    context_block = ""
    if context_globs:
        project_root = os.getcwd()
        max_tokens = cfg["runtime"]["context_max_tokens"]
        context_block = _build_context_section(context_globs, project_root, max_tokens)

    # --- body heading ---
    # runner.py always uses f"# Agent: {name}\n\n{body}" for all definition
    # types (agents, skills, and prompts all go through run_agent).
    display_name = frontmatter.get("name", name)
    if kind == "prompt":
        # Prompts have no H1 heading prefix in the runner; body is used verbatim.
        body_heading = body
    else:
        body_heading = f"# Agent: {display_name}\n\n{body}"

    # --- memory ---
    memory_dir = cfg["dirs"].get("memory", ".uio/memory")
    memory_block = build_memory_section(memory_dir)

    # ------------------------------------------------------------------ output
    parts: list[str] = []

    parts.append(_section(_MARKER_PREAMBLE, preamble, raw))

    if attribution_block:
        parts.append(_section(_MARKER_ATTRIBUTION, attribution_block, raw))

    if context_block:
        parts.append(_section(_MARKER_CONTEXT, context_block, raw))

    parts.append(_section(_MARKER_BODY, body_heading, raw))

    if memory_block:
        parts.append(_section(_MARKER_MEMORY, memory_block.rstrip(), raw))

    separator = "" if raw else "\n"
    click.echo(separator.join(parts).rstrip())


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group("explain", no_args_is_help=True)
def explain_group() -> None:
    """Show the full system prompt for an agent, skill, or prompt.

    Output is annotated with section markers (--- preamble ---, --- body ---,
    etc.) so you can see exactly what the model receives.  Pass --raw to strip
    the markers for copy/paste into an external playground.

    \\b
    Examples:
      uio explain agent my-agent
      uio explain skill summarise
      uio explain prompt daily-standup
      uio explain agent my-agent --raw
    """


@explain_group.command("agent")
@click.argument("agent_name", metavar="AGENT")
@click.option(
    "--raw",
    is_flag=True,
    default=False,
    help="Strip section markers — plain prompt text only.",
)
def explain_agent_cmd(agent_name: str, raw: bool) -> None:
    """Show the full system prompt for AGENT.

    \\b
    Examples:
      uio explain agent my-agent
      uio explain agent my-agent --raw
    """
    cfg = load_config()
    agents_dir = cfg["dirs"]["agents"]
    definition_path = f"{agents_dir}/{agent_name}.agent.md"
    try:
        _explain_definition("agent", agent_name, definition_path, raw, cfg)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@explain_group.command("skill")
@click.argument("skill_name", metavar="SKILL")
@click.option(
    "--raw",
    is_flag=True,
    default=False,
    help="Strip section markers — plain prompt text only.",
)
def explain_skill_cmd(skill_name: str, raw: bool) -> None:
    """Show the full system prompt for SKILL.

    \\b
    Examples:
      uio explain skill summarise
      uio explain skill summarise --raw
    """
    cfg = load_config()
    skills_dir = cfg["dirs"]["skills"]
    definition_path = f"{skills_dir}/{skill_name}.skill.md"
    try:
        _explain_definition("skill", skill_name, definition_path, raw, cfg)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@explain_group.command("prompt")
@click.argument("prompt_name", metavar="PROMPT")
@click.option(
    "--raw",
    is_flag=True,
    default=False,
    help="Strip section markers — plain prompt text only.",
)
def explain_prompt_cmd(prompt_name: str, raw: bool) -> None:
    """Show the full system prompt for PROMPT.

    \\b
    Examples:
      uio explain prompt daily-standup
      uio explain prompt daily-standup --raw
    """
    cfg = load_config()
    prompts_dir = cfg["dirs"]["prompts"]
    definition_path = f"{prompts_dir}/{prompt_name}.prompt.md"
    try:
        _explain_definition("prompt", prompt_name, definition_path, raw, cfg)
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc
