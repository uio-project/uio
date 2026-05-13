"""uio explain subcommands: agent, skill, prompt.

Renders the complete system prompt that would be sent to the provider for a
given agent, skill, or prompt definition, annotated with section markers.
Use --raw to strip the markers for copy/paste into an external playground.
"""

from __future__ import annotations

import glob as _glob
import os
from pathlib import Path

import click

from uio.config import load_config
from uio.core.attribution import build_attribution_instructions
from uio.core.memory import build_memory_section
from uio.core.runner import _build_preamble
from uio.schema.parser import parse_definition_file

# Marker strings used to annotate each section.
_MARKER_PREAMBLE = "--- preamble ---"
_MARKER_BODY = "--- body ---"
_MARKER_CONTEXT = "--- context: {name} ---"
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
    preamble = _build_preamble(has_mcp=True)

    # --- attribution (only for vcs-identity agents) ---
    from uio.core.identities import KNOWN_ROLES

    role = frontmatter.get("vcs-identity") or frontmatter.get("github-identity")
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

    # Resolve context files individually so we can emit per-file markers.
    context_parts: list[tuple[str, str]] = []
    if context_globs:
        project_root = os.getcwd()
        max_tokens = cfg["runtime"]["context_max_tokens"]
        seen: set[str] = set()
        total_tokens = 0
        cap_reached = False
        from uio.core.memory import estimate_tokens

        for pattern in context_globs:
            if cap_reached:
                break
            matched = sorted(_glob.glob(os.path.join(project_root, pattern), recursive=True))
            for fpath in matched:
                if cap_reached:
                    break
                if not os.path.isfile(fpath):
                    continue
                real = os.path.realpath(fpath)
                if real in seen:
                    continue
                seen.add(real)
                try:
                    with open(fpath, encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                except OSError:
                    continue

                file_tokens = estimate_tokens(content)
                rel_path = os.path.relpath(fpath, project_root)
                remaining = max_tokens - total_tokens

                if file_tokens <= remaining:
                    context_parts.append((rel_path, content))
                    total_tokens += file_tokens
                    if total_tokens >= max_tokens:
                        cap_reached = True
                else:
                    cutoff = remaining * 4
                    omitted = file_tokens - remaining
                    truncated = f"{content[:cutoff]}\n[truncated — {omitted} tokens omitted]"
                    context_parts.append((rel_path, truncated))
                    cap_reached = True

    # --- body heading (matches runner.py "_agent_header") ---
    display_name = frontmatter.get("name", name)
    if kind == "agent":
        body_heading = f"# Agent: {display_name}\n\n{body}"
    elif kind == "skill":
        body_heading = f"# Skill: {display_name}\n\n{body}"
    else:
        # prompts have no H1 heading prefix in the runner; body is used verbatim
        body_heading = body

    # --- memory ---
    memory_dir = cfg["dirs"].get("memory", ".uio/memory")
    memory_block = build_memory_section(memory_dir)

    # ------------------------------------------------------------------ output
    parts: list[str] = []

    parts.append(_section(_MARKER_PREAMBLE, preamble, raw))

    if attribution_block:
        parts.append(_section(_MARKER_ATTRIBUTION, attribution_block, raw))

    for rel_path, file_content in context_parts:
        marker = _MARKER_CONTEXT.format(name=rel_path)
        parts.append(_section(marker, file_content, raw))

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
