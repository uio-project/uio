"""Tests for workflow definition parsing and execution."""

from __future__ import annotations

import textwrap
from unittest.mock import patch

from uio.core.workflow import _eval_when, _interpolate, parse_workflow_steps, run_workflow
from uio.schema.parser import check_workflow_steps, validate_workflow_definition


# ---------------------------------------------------------------------------
# parse_workflow_steps
# ---------------------------------------------------------------------------


def test_parse_workflow_steps_empty():
    assert parse_workflow_steps({}) == []
    assert parse_workflow_steps({"steps": []}) == []


def test_parse_workflow_steps_agent_step():
    fm = {
        "steps": [{"name": "review", "agent": "reviewer", "arg": "{{ input }}", "output": "result"}]
    }
    steps = parse_workflow_steps(fm)
    assert len(steps) == 1
    assert steps[0].name == "review"
    assert steps[0].agent == "reviewer"
    assert steps[0].skill is None
    assert steps[0].arg == "{{ input }}"
    assert steps[0].output == "result"
    assert steps[0].when is None


def test_parse_workflow_steps_skill_step():
    fm = {"steps": [{"name": "summarise", "skill": "summarise", "arg": "{{ review_result }}"}]}
    steps = parse_workflow_steps(fm)
    assert steps[0].skill == "summarise"
    assert steps[0].agent is None


def test_parse_workflow_steps_with_when():
    fm = {"steps": [{"name": "fix", "agent": "coder", "when": "result contains BLOCKER"}]}
    steps = parse_workflow_steps(fm)
    assert steps[0].when == "result contains BLOCKER"


def test_parse_workflow_steps_skips_non_dicts():
    fm = {"steps": ["not-a-dict", {"name": "ok", "agent": "coder"}]}
    steps = parse_workflow_steps(fm)
    assert len(steps) == 1
    assert steps[0].name == "ok"


# ---------------------------------------------------------------------------
# _interpolate
# ---------------------------------------------------------------------------


def test_interpolate_replaces_input():
    result = _interpolate("run against {{ input }}", {"input": "owner/repo#1"})
    assert result == "run against owner/repo#1"


def test_interpolate_replaces_multiple():
    result = _interpolate("{{ a }} and {{ b }}", {"a": "X", "b": "Y"})
    assert result == "X and Y"


def test_interpolate_unknown_variable_preserved():
    result = _interpolate("hello {{ unknown }}", {})
    assert result == "hello {{ unknown }}"


def test_interpolate_whitespace_in_braces():
    result = _interpolate("{{  input  }}", {"input": "val"})
    assert result == "val"


# ---------------------------------------------------------------------------
# _eval_when
# ---------------------------------------------------------------------------


def test_eval_when_substring_present():
    variables = {"review_result": "This has a BLOCKER in it"}
    assert _eval_when("review_result contains BLOCKER", variables) is True


def test_eval_when_substring_absent():
    variables = {"review_result": "All good, no issues."}
    assert _eval_when("review_result contains BLOCKER", variables) is False


def test_eval_when_case_insensitive():
    variables = {"result": "found a blocker here"}
    assert _eval_when("result contains BLOCKER", variables) is True


def test_eval_when_variable_missing_returns_false():
    assert _eval_when("missing_var contains foo", {}) is False


def test_eval_when_quoted_substring():
    variables = {"out": "critical: BLOCKER detected"}
    assert _eval_when('out contains "BLOCKER"', variables) is True


def test_eval_when_bad_syntax_returns_true(capsys):
    result = _eval_when("this-is-bad-syntax", {})
    assert result is True
    captured = capsys.readouterr()
    assert "unrecognised" in captured.err


# ---------------------------------------------------------------------------
# validate_workflow_definition
# ---------------------------------------------------------------------------


def test_validate_workflow_valid(tmp_path):
    f = tmp_path / "my.workflow.md"
    f.write_text("---\nname: My Workflow\ndescription: Does stuff.\nsteps: []\n---\nBody.\n")
    from uio.schema.parser import parse_definition_file

    fm, _ = parse_definition_file(str(f))
    errors = validate_workflow_definition(str(f), fm)
    assert errors == []


def test_validate_workflow_missing_name(tmp_path):
    f = tmp_path / "w.workflow.md"
    f.write_text("---\ndescription: No name.\n---\nBody.\n")
    from uio.schema.parser import parse_definition_file

    fm, _ = parse_definition_file(str(f))
    errors = validate_workflow_definition(str(f), fm)
    assert any("name" in e for e in errors)


def test_validate_workflow_missing_description(tmp_path):
    f = tmp_path / "w.workflow.md"
    f.write_text("---\nname: W\n---\nBody.\n")
    from uio.schema.parser import parse_definition_file

    fm, _ = parse_definition_file(str(f))
    errors = validate_workflow_definition(str(f), fm)
    assert any("description" in e for e in errors)


def test_validate_workflow_unknown_key(tmp_path):
    f = tmp_path / "w.workflow.md"
    f.write_text("---\nname: W\ndescription: D.\nunknown_key: bad\n---\nBody.\n")
    from uio.schema.parser import parse_definition_file

    fm, _ = parse_definition_file(str(f))
    errors = validate_workflow_definition(str(f), fm)
    assert any("unknown_key" in e for e in errors)


def test_validate_workflow_steps_not_list(tmp_path):
    f = tmp_path / "w.workflow.md"
    f.write_text("---\nname: W\ndescription: D.\nsteps: not-a-list\n---\nBody.\n")
    from uio.schema.parser import parse_definition_file

    fm, _ = parse_definition_file(str(f))
    errors = validate_workflow_definition(str(f), fm)
    assert any("steps" in e for e in errors)


# ---------------------------------------------------------------------------
# check_workflow_steps
# ---------------------------------------------------------------------------


def test_check_workflow_steps_valid():
    fm = {
        "steps": [
            {"name": "review", "agent": "reviewer", "arg": "{{ input }}", "output": "r"},
            {"name": "fix", "skill": "fixer", "when": "r contains X"},
        ]
    }
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert warnings == []


def test_check_workflow_steps_both_agent_and_skill():
    fm = {"steps": [{"name": "s", "agent": "a", "skill": "b"}]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert any("mutually exclusive" in w for w in warnings)


def test_check_workflow_steps_no_step_type():
    fm = {"steps": [{"name": "s"}]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert any("neither" in w for w in warnings)


def test_check_workflow_steps_skill_and_prompt_mutually_exclusive():
    fm = {"steps": [{"name": "s", "skill": "a", "prompt": "p"}]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert any("mutually exclusive" in w for w in warnings)


def test_check_workflow_steps_unknown_key():
    fm = {"steps": [{"name": "s", "agent": "a", "typo_key": "val"}]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert any("typo_key" in w for w in warnings)


def test_check_workflow_steps_non_dict_step():
    fm = {"steps": ["not-a-dict"]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert any("not a mapping" in w for w in warnings)


# ---------------------------------------------------------------------------
# workflow list CLI
# ---------------------------------------------------------------------------


def test_workflow_list_no_workflows(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from uio.cli.workflow import workflow_list_cmd

    cfg = {
        "dirs": {
            "workflows": str(tmp_path / "workflows"),
        }
    }
    monkeypatch.setattr("uio.cli.workflow.load_config", lambda: cfg)
    runner = CliRunner()
    result = runner.invoke(workflow_list_cmd, [])
    assert result.exit_code == 0
    assert "No workflows found" in result.output


def test_workflow_list_shows_workflows(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from uio.cli.workflow import workflow_list_cmd

    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir()
    (wf_dir / "review-and-fix.workflow.md").write_text(
        textwrap.dedent("""\
            ---
            name: review-and-fix
            description: Review a PR and open a fix branch.
            steps:
              - name: review
                agent: reviewer
                arg: "{{ input }}"
              - name: fix
                agent: coder
                arg: "{{ input }}"
                when: "review_result contains BLOCKER"
            ---

            # Workflow: review-and-fix

            Body text here.
        """)
    )

    cfg = {"dirs": {"workflows": str(wf_dir)}}
    monkeypatch.setattr("uio.cli.workflow.load_config", lambda: cfg)
    runner = CliRunner()
    result = runner.invoke(workflow_list_cmd, [])
    assert result.exit_code == 0
    assert "review-and-fix" in result.output
    assert "Review a PR" in result.output
    assert "2" in result.output  # step count


# ---------------------------------------------------------------------------
# run_workflow execution
# ---------------------------------------------------------------------------

_MINIMAL_CFG: dict = {
    "dirs": {
        "agents": ".uio/agents",
        "skills": ".uio/skills",
        "prompts": ".uio/prompts",
        "workflows": ".uio/workflows",
        "memory": None,
    },
    "runtime": {
        "default_provider": None,
        "timeout": 10,
        "max_iterations": 5,
        "max_iterations_large": 10,
        "cost_ledger": "uio_cost.jsonl",
        "routing_chain": None,
        "context_max_tokens": 1000,
        "anthropic_max_tokens": None,
    },
    "large_agents": {"names": []},
    "attribution": {"enabled": True},
    "mcp": {},
    "mcp_plugins": [],
}


def _make_cfg(tmp_path) -> dict:
    cfg = {k: dict(v) if isinstance(v, dict) else v for k, v in _MINIMAL_CFG.items()}
    cfg["dirs"] = dict(_MINIMAL_CFG["dirs"])
    cfg["dirs"]["workflows"] = str(tmp_path / "workflows")
    cfg["dirs"]["agents"] = str(tmp_path / "agents")
    cfg["dirs"]["skills"] = str(tmp_path / "skills")
    cfg["dirs"]["prompts"] = str(tmp_path / "prompts")
    return cfg


def _write_workflow(tmp_path, name: str, content: str) -> None:
    wf_dir = tmp_path / "workflows"
    wf_dir.mkdir(exist_ok=True)
    (wf_dir / f"{name}.workflow.md").write_text(content)


def test_run_workflow_sequences_and_threads_output(tmp_path):
    _write_workflow(
        tmp_path,
        "seq",
        textwrap.dedent("""\
            ---
            name: seq
            description: D.
            steps:
              - name: step-a
                agent: agent-a
                arg: "{{ input }}"
                output: result_a
              - name: step-b
                agent: agent-b
                arg: "{{ result_a }}"
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    calls: list[tuple[str, str | None]] = []

    def fake_run_agent(name, arg, **kwargs):
        calls.append((name, arg))
        return f"output-of-{name}"

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("seq", "my-input", cfg=cfg)

    assert calls[0] == ("agent-a", "my-input")
    assert calls[1] == ("agent-b", "output-of-agent-a")  # output threaded


def test_run_workflow_when_condition_skips_step(tmp_path):
    _write_workflow(
        tmp_path,
        "cond",
        textwrap.dedent("""\
            ---
            name: cond
            description: D.
            steps:
              - name: check
                agent: checker
                arg: "{{ input }}"
                output: check_result
              - name: fix
                agent: fixer
                arg: "{{ input }}"
                when: "check_result contains BLOCKER"
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    calls: list[str] = []

    def fake_run_agent(name, arg, **kwargs):
        calls.append(name)
        return "All good, no issues."

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("cond", "pr-ref", cfg=cfg)

    assert calls == ["checker"]  # fixer was skipped — no BLOCKER in output


def test_run_workflow_when_condition_runs_step(tmp_path):
    _write_workflow(
        tmp_path,
        "cond2",
        textwrap.dedent("""\
            ---
            name: cond2
            description: D.
            steps:
              - name: check
                agent: checker
                arg: "{{ input }}"
                output: check_result
              - name: fix
                agent: fixer
                arg: "{{ input }}"
                when: "check_result contains BLOCKER"
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    calls: list[str] = []

    def fake_run_agent(name, arg, **kwargs):
        calls.append(name)
        return "Found a BLOCKER in the diff."

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("cond2", "pr-ref", cfg=cfg)

    assert calls == ["checker", "fixer"]  # fixer ran — BLOCKER present


def test_run_workflow_warns_on_none_output(tmp_path, capsys):
    _write_workflow(
        tmp_path,
        "cap",
        textwrap.dedent("""\
            ---
            name: cap
            description: D.
            steps:
              - name: capped
                agent: slow-agent
                arg: "{{ input }}"
                output: capped_result
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)

    def fake_run_agent(name, arg, **kwargs):
        return None  # simulates iteration cap

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("cap", "arg", cfg=cfg)

    captured = capsys.readouterr()
    assert "Warning" in captured.err
    assert "capped_result" in captured.err


def test_run_workflow_no_steps(tmp_path, capsys):
    _write_workflow(
        tmp_path,
        "empty",
        textwrap.dedent("""\
            ---
            name: empty
            description: D.
            steps: []
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    with patch("uio.core.runner.run_agent") as mock_agent:
        run_workflow("empty", None, cfg=cfg)
        mock_agent.assert_not_called()


def test_run_workflow_skill_step(tmp_path):
    _write_workflow(
        tmp_path,
        "skill-wf",
        textwrap.dedent("""\
            ---
            name: skill-wf
            description: D.
            steps:
              - name: summarise
                skill: summarise
                arg: "{{ input }}"
                output: summary
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_run_agent(name, arg, **kwargs):
        calls.append((name, kwargs.get("definition_path", "")))
        return "the summary"

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("skill-wf", "some text", cfg=cfg)

    assert calls[0][0] == "summarise"
    assert ".skill.md" in calls[0][1]  # resolved as a skill, not an agent


def test_parse_workflow_steps_prompt_step():
    fm = {
        "steps": [
            {
                "name": "summarise",
                "prompt": "summarise-pr",
                "arg": "{{ input }}",
                "output": "summary",
            }
        ]
    }
    steps = parse_workflow_steps(fm)
    assert len(steps) == 1
    assert steps[0].prompt == "summarise-pr"
    assert steps[0].agent is None
    assert steps[0].skill is None
    assert steps[0].output == "summary"


def test_run_workflow_prompt_step(tmp_path):
    _write_workflow(
        tmp_path,
        "prompt-wf",
        textwrap.dedent("""\
            ---
            name: prompt-wf
            description: D.
            steps:
              - name: summarise
                prompt: summarise-pr
                arg: "{{ input }}"
                output: summary
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_run_agent(name, arg, **kwargs):
        calls.append((name, kwargs.get("definition_path", "")))
        return "the summary"

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("prompt-wf", "some text", cfg=cfg)

    assert calls[0][0] == "summarise-pr"
    assert ".prompt.md" in calls[0][1]  # resolved as a prompt


def test_check_workflow_steps_prompt_step_valid():
    fm = {"steps": [{"name": "s", "prompt": "my-prompt", "arg": "{{ input }}"}]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert warnings == []


def test_check_workflow_steps_prompt_and_agent_mutually_exclusive():
    fm = {"steps": [{"name": "s", "agent": "a", "prompt": "p"}]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert any("mutually exclusive" in w for w in warnings)


def test_run_workflow_passes_workflow_and_run_id_to_run_agent(tmp_path):
    _write_workflow(
        tmp_path,
        "wf",
        textwrap.dedent("""\
            ---
            name: wf
            description: D.
            steps:
              - name: s
                agent: my-agent
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    captured_kwargs: list[dict] = []

    def fake_run_agent(name, arg, **kwargs):
        captured_kwargs.append(kwargs)
        return None

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("wf", None, cfg=cfg)

    assert captured_kwargs[0]["workflow"] == "wf"
    assert "workflow_run_id" in captured_kwargs[0]
    import uuid as _uuid

    _uuid.UUID(captured_kwargs[0]["workflow_run_id"], version=4)


def test_run_workflow_all_steps_share_same_run_id(tmp_path):
    _write_workflow(
        tmp_path,
        "multi",
        textwrap.dedent("""\
            ---
            name: multi
            description: D.
            steps:
              - name: step-a
                agent: agent-a
              - name: step-b
                agent: agent-b
            ---
            Body.
        """),
    )
    cfg = _make_cfg(tmp_path)
    run_ids: list[str] = []

    def fake_run_agent(name, arg, **kwargs):
        run_ids.append(kwargs.get("workflow_run_id", ""))
        return None

    with patch("uio.core.runner.run_agent", side_effect=fake_run_agent):
        run_workflow("multi", None, cfg=cfg)

    assert len(run_ids) == 2
    assert run_ids[0] == run_ids[1], "all steps must share the same workflow_run_id"
