"""Sequential workflow execution for *.workflow.md definitions."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

from uio.schema.parser import parse_definition_file

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_WHEN_RE = re.compile(r"^(\w+)\s+contains\s+(.+)$", re.IGNORECASE)


@dataclass
class WorkflowStep:
    name: str
    agent: str | None = None
    skill: str | None = None
    arg: str | None = None
    output: str | None = None
    when: str | None = None


def parse_workflow_steps(frontmatter: dict) -> list[WorkflowStep]:
    raw = frontmatter.get("steps") or []
    steps = []
    for s in raw:
        if not isinstance(s, dict):
            continue
        steps.append(
            WorkflowStep(
                name=s.get("name", ""),
                agent=s.get("agent"),
                skill=s.get("skill"),
                arg=s.get("arg"),
                output=s.get("output"),
                when=s.get("when"),
            )
        )
    return steps


def _interpolate(template: str, variables: dict[str, str]) -> str:
    def replace(m: re.Match) -> str:
        return variables.get(m.group(1), m.group(0))

    return _VAR_RE.sub(replace, template)


def _eval_when(condition: str, variables: dict[str, str]) -> bool:
    """Return True when the step should run (condition is satisfied)."""
    m = _WHEN_RE.match(condition.strip())
    if not m:
        print(
            f"  [workflow] Warning: unrecognised 'when:' syntax: {condition!r}",
            file=sys.stderr,
        )
        return True
    var_name = m.group(1)
    substring = m.group(2).strip().strip("\"'")
    value = variables.get(var_name, "")
    return substring.lower() in value.lower()


def run_workflow(
    workflow_name: str,
    arg: str | None,
    *,
    cfg: dict,
    provider: str | None = None,
    model: str | None = None,
    no_mcp: bool = False,
    shell: str | None = None,
) -> None:
    from uio.core.runner import GuardrailError, run_agent

    workflows_dir = cfg["dirs"]["workflows"]
    path = f"{workflows_dir}/{workflow_name}.workflow.md"

    if not os.path.exists(path):
        sys.exit(f"Error: workflow not found: {path}")

    fm, _ = parse_definition_file(path)
    steps = parse_workflow_steps(fm)

    if not steps:
        print("  [workflow] No steps defined. Nothing to do.")
        return

    variables: dict[str, str] = {"input": arg or ""}

    print(f"\n🔄 Workflow: {fm.get('name', workflow_name)}")
    print(f"   Steps: {len(steps)}")
    if arg:
        print(f"   Input: {arg}")
    print()

    for i, step in enumerate(steps, 1):
        print(f"[step {i}/{len(steps)}: {step.name}]")

        if step.when and not _eval_when(step.when, variables):
            print(f"  Skipped — when: '{step.when}' not satisfied\n")
            continue

        if step.agent:
            def_path = f"{cfg['dirs']['agents']}/{step.agent}.agent.md"
            runner_name = step.agent
        elif step.skill:
            def_path = f"{cfg['dirs']['skills']}/{step.skill}.skill.md"
            runner_name = step.skill
        else:
            print(
                f"  [workflow] Error: step '{step.name}' has neither 'agent' nor 'skill'",
                file=sys.stderr,
            )
            sys.exit(1)

        step_arg = _interpolate(step.arg, variables) if step.arg else arg

        try:
            result = run_agent(
                runner_name,
                step_arg,
                provider=provider or cfg["runtime"].get("default_provider"),
                model=model,
                timeout=cfg["runtime"]["timeout"],
                no_mcp=no_mcp,
                mcp_cfg=cfg["mcp"],
                mcp_plugins=cfg.get("mcp_plugins", []),
                definition_path=def_path,
                ledger_path=cfg["runtime"]["cost_ledger"],
                large_agent_names=cfg["large_agents"]["names"],
                shell_override=shell,
                max_iterations=cfg["runtime"]["max_iterations"],
                max_iterations_large=cfg["runtime"]["max_iterations_large"],
                anthropic_max_tokens=cfg["runtime"].get("anthropic_max_tokens"),
                routing_chain=cfg["runtime"].get("routing_chain"),
                memory_dir=cfg["dirs"]["memory"],
                context_max_tokens=cfg["runtime"]["context_max_tokens"],
            )
        except GuardrailError as exc:
            print(f"\n❌ Workflow halted at step '{step.name}': guardrail — {exc}", file=sys.stderr)
            sys.exit(1)
        except SystemExit as exc:
            print(f"\n❌ Workflow halted at step '{step.name}': {exc}", file=sys.stderr)
            raise

        if step.output is not None and result is not None:
            variables[step.output] = result
            print(f"  → captured output as '${step.output}'\n")

    print("\n✅ Workflow complete.")
