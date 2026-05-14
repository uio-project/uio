"""Root CLI group and top-level commands: init, validate, completion."""

from __future__ import annotations

import sys
from glob import glob
from pathlib import Path

import click

from uio import __version__
from uio.cli.agent import agent_group
from uio.cli.chat import chat_cmd
from uio.cli.config import config_group
from uio.cli.cost import cost_cmd
from uio.cli.explain import explain_group
from uio.cli.link import link_cmd
from uio.cli.mcp import mcp_group
from uio.cli.memory import memory_group
from uio.cli.prompt import prompt_group
from uio.cli.registry import registry_group
from uio.cli.skill import skill_group
from uio.cli.workflow import workflow_group
from uio.config import load_config
from uio.examples import EXAMPLES
from uio.schema.parser import (
    check_heading_format,
    check_identity_env,
    check_inheritance_cycles,
    check_minimal_body,
    check_schema_support,
    check_skill_interface_sections,
    check_skill_references,
    check_stopping_criteria,
    check_thinking_complexity,
    check_unknown_keys,
    check_workflow_steps,
    parse_definition_file,
    validate_definition,
    validate_workflow_definition,
)

_EXAMPLE_AGENT = """\
---
name: Example Agent
description: A starter agent — edit to fit your workflow.
complexity: small
tools:
  - terminal
---

# Agent: Example Agent

Your task is to …
"""

_EXAMPLE_SKILL = """\
---
name: Example Skill
description: A starter skill — edit to fit your workflow.
---

# Skill: Example Skill

Your task is to …
"""

_EXAMPLE_PROMPT = """\
---
name: example-prompt
description: A starter prompt — edit to fit your workflow.
argument-hint: "[optional-arg]"
invokable: true
---

Your task is to …
"""


@click.group(no_args_is_help=True)
@click.version_option(__version__, prog_name="uio")
def main() -> None:
    """uio — provider-agnostic AI agent/skill/prompt runner."""


main.add_command(agent_group, "agent")
main.add_command(skill_group, "skill")
main.add_command(prompt_group, "prompt")
main.add_command(workflow_group, "workflow")
main.add_command(explain_group, "explain")
main.add_command(chat_cmd, "chat")
main.add_command(cost_cmd, "cost")
main.add_command(config_group, "config")
main.add_command(link_cmd, "link")
main.add_command(memory_group, "memory")
main.add_command(registry_group, "registry")
main.add_command(mcp_group, "mcp")


@main.command("init")
@click.option(
    "--examples",
    is_flag=True,
    default=False,
    help="Also install bundled example agents, skills, and prompts.",
)
def init_cmd(examples: bool) -> None:
    """Scaffold .uio/ with an example agent, skill, and prompt.

    Pass --examples to also install the bundled real-world examples
    (summarise, explain-code, shell-helper, etc.).

    Also adds uio_cost.jsonl to .gitignore if one exists.

    \b
    Examples:
      uio init
      uio init --examples
    """
    cfg = load_config()
    agents_dir = Path(cfg["dirs"]["agents"])
    skills_dir = Path(cfg["dirs"]["skills"])
    prompts_dir = Path(cfg["dirs"]["prompts"])
    workflows_dir = Path(cfg["dirs"]["workflows"])
    memory_dir = Path(cfg["dirs"]["memory"])

    for d in (agents_dir, skills_dir, prompts_dir, workflows_dir, memory_dir):
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"  Created directory: {d}/")

    agent_file = agents_dir / "example.agent.md"
    if not agent_file.exists():
        agent_file.write_text(_EXAMPLE_AGENT)
        click.echo(f"  Created: {agent_file}")

    skill_file = skills_dir / "example.skill.md"
    if not skill_file.exists():
        skill_file.write_text(_EXAMPLE_SKILL)
        click.echo(f"  Created: {skill_file}")

    prompt_file = prompts_dir / "example.prompt.md"
    if not prompt_file.exists():
        prompt_file.write_text(_EXAMPLE_PROMPT)
        click.echo(f"  Created: {prompt_file}")

    if examples:
        dir_map = {
            "agents": agents_dir,
            "skills": skills_dir,
            "prompts": prompts_dir,
        }
        for kind, entries in EXAMPLES.items():
            dest_dir = dir_map[kind]
            for filename, content in entries:
                dest = dest_dir / filename
                if not dest.exists():
                    dest.write_text(content)
                    click.echo(f"  Created: {dest}")
                else:
                    click.echo(f"  Skipped (exists): {dest}")

    # Add generated files to .gitignore if one exists
    ledger = cfg["runtime"]["cost_ledger"]
    gitignore = Path(".gitignore")
    if gitignore.exists():
        contents = gitignore.read_text()
        with gitignore.open("a") as f:
            if ledger not in contents:
                f.write(f"\n# uio cost ledger\n{ledger}\n")
                click.echo(f"  Added '{ledger}' to .gitignore")
            if ".mcp.json" not in contents:
                f.write("\n# uio mcp init output (env var refs vary per developer)\n.mcp.json\n")
                click.echo("  Added '.mcp.json' to .gitignore")

    click.echo("\nDone. Run 'uio agent list' to see available agents.")


@main.command("validate")
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Enable opt-in checks (e.g. stopping-criteria detection).",
)
def validate_cmd(strict: bool) -> None:
    """Parse all definition files and check required frontmatter fields.

    Exits non-zero if any errors are found.

    Pass --strict to enable additional opt-in checks such as stopping-criteria
    detection.

    Example:

    \b
      uio validate
      uio validate --strict
    """
    cfg = load_config()
    skills_dir = cfg["dirs"]["skills"]
    default_provider: str | None = cfg["runtime"].get("default_provider")
    agent_skill_prompt_patterns = [
        (cfg["dirs"]["agents"], "*.agent.md"),
        (skills_dir, "*.skill.md"),
        (cfg["dirs"]["prompts"], "*.prompt.md"),
    ]
    workflow_patterns = [
        (cfg["dirs"]["workflows"], "*.workflow.md"),
    ]

    errors: list[str] = []
    warnings: list[str] = []
    total = 0
    all_definition_paths: list[str] = []

    for directory, pattern in agent_skill_prompt_patterns:
        for path in sorted(glob(f"{directory}/{pattern}")):
            total += 1
            all_definition_paths.append(path)
            try:
                fm, body = parse_definition_file(path)
            except Exception as e:
                errors.append(f"{path}: could not parse: {e}")
                continue
            errors.extend(validate_definition(path, fm))
            warnings.extend(check_unknown_keys(path, fm))
            warnings.extend(check_identity_env(path, fm))
            warnings.extend(check_heading_format(path, fm, body))
            warnings.extend(check_skill_references(path, body, skills_dir))
            warnings.extend(check_thinking_complexity(path, fm))
            warnings.extend(check_skill_interface_sections(path, body))
            warnings.extend(check_minimal_body(path, body))
            warnings.extend(check_schema_support(path, fm, default_provider))
            if strict:
                warnings.extend(check_stopping_criteria(path, body))

    for directory, pattern in workflow_patterns:
        for path in sorted(glob(f"{directory}/{pattern}")):
            total += 1
            try:
                fm, _ = parse_definition_file(path)
            except Exception as e:
                errors.append(f"{path}: could not parse: {e}")
                continue
            errors.extend(validate_workflow_definition(path, fm))
            warnings.extend(check_unknown_keys(path, fm))
            warnings.extend(check_workflow_steps(path, fm))

    # Resolve inheritance chains and warn on cycles / missing parents
    warnings.extend(check_inheritance_cycles(all_definition_paths))

    if total == 0:
        click.echo("  No definition files found.")
        return

    for warn in warnings:
        click.echo(f"  WARNING: {warn}", err=True)

    if errors:
        for err in errors:
            click.echo(f"  ERROR: {err}", err=True)
        click.echo(f"\n{len(errors)} error(s) in {total} file(s).", err=True)
        sys.exit(1)

    if warnings:
        click.echo(f"  OK — {total} definition file(s) valid ({len(warnings)} warning(s)).")
    else:
        click.echo(f"  OK — {total} definition file(s) valid.")


@main.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish", "pwsh"]), default="bash")
def completion_cmd(shell: str) -> None:
    """Print a shell completion script.

    \b
    Examples:
      bash:  eval "$(uio completion bash)"
      zsh:   eval "$(uio completion zsh)"
      fish:  uio completion fish | source
      pwsh:  uio completion pwsh | Out-String | Invoke-Expression
    """
    try:
        from click.shell_completion import BashComplete, FishComplete, ZshComplete

        if shell == "pwsh":
            try:
                from click.shell_completion import PowerShellComplete

                sc = PowerShellComplete(main, {}, "uio", "_UIO_COMPLETE")
            except ImportError:
                raise click.ClickException(
                    "PowerShell completion requires Click 8.0+. "
                    "Upgrade with: pip install --upgrade click"
                )
        else:
            cls = {"bash": BashComplete, "zsh": ZshComplete, "fish": FishComplete}[shell]
            sc = cls(main, {}, "uio", "_UIO_COMPLETE")
        click.echo(sc.source())
    except (ImportError, AttributeError) as e:
        raise click.ClickException(f"Shell completion unavailable: {e}")
