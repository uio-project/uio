"""Tests for the YAML frontmatter parser."""
import textwrap

import pytest

from uio.schema.parser import parse_definition_file, validate_definition


def test_standard_frontmatter(tmp_path):
    content = textwrap.dedent("""\
        ---
        name: My Agent
        description: A test agent.
        tools:
          - terminal
        ---
        # Agent: My Agent

        Do the task.
    """)
    f = tmp_path / "my-agent.agent.md"
    f.write_text(content)
    fm, body = parse_definition_file(str(f))
    assert fm["name"] == "My Agent"
    assert fm["description"] == "A test agent."
    assert fm["tools"] == ["terminal"]
    assert "Do the task." in body


def test_no_frontmatter(tmp_path):
    content = "Just some markdown.\n\nNo frontmatter here."
    f = tmp_path / "bare.agent.md"
    f.write_text(content)
    fm, body = parse_definition_file(str(f))
    assert fm == {}
    assert "No frontmatter here." in body


def test_body_is_stripped(tmp_path):
    f = tmp_path / "test.agent.md"
    f.write_text("---\nname: Test\n---\n\n\n  body text  \n")
    _, body = parse_definition_file(str(f))
    assert body == "body text"


def test_multiline_body(tmp_path):
    content = textwrap.dedent("""\
        ---
        name: Manager
        description: A manager.
        ---
        ## Workflow

        Step 1.
        Step 2.
    """)
    f = tmp_path / "manager.agent.md"
    f.write_text(content)
    _, body = parse_definition_file(str(f))
    assert "Step 1." in body
    assert "Step 2." in body


def test_frontmatter_only_name(tmp_path):
    f = tmp_path / "minimal.agent.md"
    f.write_text("---\nname: Minimal\n---\nBody here.")
    fm, body = parse_definition_file(str(f))
    assert fm == {"name": "Minimal"}
    assert body == "Body here."


def test_validate_valid_definition(tmp_path):
    f = tmp_path / "ok.agent.md"
    f.write_text("---\nname: OK\ndescription: Fine.\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert errors == []


def test_validate_missing_name(tmp_path):
    f = tmp_path / "bad.agent.md"
    f.write_text("---\ndescription: No name.\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert any("name" in e for e in errors)


def test_validate_missing_description(tmp_path):
    f = tmp_path / "bad.agent.md"
    f.write_text("---\nname: NoDesc\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert any("description" in e for e in errors)


def test_validate_unknown_key_warns(tmp_path):
    f = tmp_path / "odd.agent.md"
    f.write_text("---\nname: Odd\ndescription: Desc.\nweird_key: value\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert any("weird_key" in e for e in errors)


def test_argument_hint_list_field(tmp_path):
    content = textwrap.dedent("""\
        ---
        name: my-prompt
        description: A prompt.
        argument-hint:
          - "[issue-number]"
          - "[repo]"
        invokable: true
        ---
        Body.
    """)
    f = tmp_path / "my-prompt.prompt.md"
    f.write_text(content)
    fm, _ = parse_definition_file(str(f))
    assert isinstance(fm["argument-hint"], list)
    assert len(fm["argument-hint"]) == 2
