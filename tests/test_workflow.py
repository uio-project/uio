"""Tests for workflow definition parsing and execution."""

from __future__ import annotations

import textwrap


from uio.core.workflow import _eval_when, _interpolate, parse_workflow_steps
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


def test_check_workflow_steps_neither_agent_nor_skill():
    fm = {"steps": [{"name": "s"}]}
    warnings = check_workflow_steps("w.workflow.md", fm)
    assert any("neither" in w for w in warnings)


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
