"""Tests for the YAML frontmatter parser."""

import textwrap


from uio.schema.parser import check_identity_env, parse_definition_file, validate_definition


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


def test_validate_github_identity_valid(tmp_path):
    f = tmp_path / "planner.agent.md"
    f.write_text("---\nname: P\ndescription: D.\ngithub-identity: planner\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert errors == []


def test_validate_github_identity_invalid_value(tmp_path):
    f = tmp_path / "bad.agent.md"
    f.write_text("---\nname: P\ndescription: D.\ngithub-identity: wizard\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert any("wizard" in e for e in errors)


def test_check_identity_env_no_identity(tmp_path):
    f = tmp_path / "no-identity.agent.md"
    f.write_text("---\nname: A\ndescription: D.\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    assert check_identity_env(str(f), fm) == []


def test_check_identity_env_vars_absent(tmp_path, monkeypatch):
    for var in (
        "GITHUB_APP_PLANNER_ID",
        "GITHUB_APP_PLANNER_INSTALLATION_ID",
        "GITHUB_APP_PLANNER_PRIVATE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    f = tmp_path / "planner.agent.md"
    f.write_text("---\nname: P\ndescription: D.\ngithub-identity: planner\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    warnings = check_identity_env(str(f), fm)
    assert len(warnings) == 1
    assert "GITHUB_APP_PLANNER_ID" in warnings[0]
    assert "planner" in warnings[0]


def test_check_identity_env_vars_present(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_APP_REVIEWER_ID", "123")
    monkeypatch.setenv("GITHUB_APP_REVIEWER_INSTALLATION_ID", "456")
    monkeypatch.setenv("GITHUB_APP_REVIEWER_PRIVATE_KEY", "fake-pem")
    f = tmp_path / "reviewer.agent.md"
    f.write_text("---\nname: R\ndescription: D.\ngithub-identity: reviewer\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    assert check_identity_env(str(f), fm) == []


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


# ---------------------------------------------------------------------------
# vcs-identity / capabilities (Phase 3 fields)
# ---------------------------------------------------------------------------


def test_validate_vcs_identity_valid(tmp_path):
    f = tmp_path / "planner.agent.md"
    f.write_text("---\nname: P\ndescription: D.\nvcs-identity: planner\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert errors == []


def test_validate_vcs_identity_invalid_value(tmp_path):
    f = tmp_path / "bad.agent.md"
    f.write_text("---\nname: P\ndescription: D.\nvcs-identity: wizard\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert any("wizard" in e for e in errors)


def test_validate_vcs_provider_accepted(tmp_path):
    f = tmp_path / "planner.agent.md"
    f.write_text(
        "---\nname: P\ndescription: D.\nvcs-identity: planner\nvcs-provider: github\n---\nBody."
    )
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert errors == []


def test_validate_capabilities_field_accepted(tmp_path):
    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\ncapabilities:\n  - vcs\n  - ci\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert errors == []


def test_validate_github_identity_still_valid(tmp_path):
    """Legacy github-identity field must not produce a validation error."""
    f = tmp_path / "legacy.agent.md"
    f.write_text("---\nname: L\ndescription: D.\ngithub-identity: coder\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert errors == []


def test_check_identity_env_uses_vcs_identity(tmp_path, monkeypatch):
    for var in (
        "GITHUB_APP_CODER_ID",
        "GITHUB_APP_CODER_INSTALLATION_ID",
        "GITHUB_APP_CODER_PRIVATE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    f = tmp_path / "coder.agent.md"
    f.write_text("---\nname: C\ndescription: D.\nvcs-identity: coder\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    warnings = check_identity_env(str(f), fm)
    assert len(warnings) == 1
    assert "vcs-identity" in warnings[0]
    assert "GITHUB_APP_CODER_ID" in warnings[0]


def test_check_identity_env_prefers_vcs_identity_over_github_identity(tmp_path, monkeypatch):
    """When both fields are present, vcs-identity takes precedence in the warning message."""
    for var in (
        "GITHUB_APP_REVIEWER_ID",
        "GITHUB_APP_REVIEWER_INSTALLATION_ID",
        "GITHUB_APP_REVIEWER_PRIVATE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    f = tmp_path / "both.agent.md"
    f.write_text(
        "---\nname: B\ndescription: D.\nvcs-identity: reviewer\ngithub-identity: reviewer\n---\nBody."
    )
    fm, _ = parse_definition_file(str(f))
    warnings = check_identity_env(str(f), fm)
    assert len(warnings) == 1
    assert "vcs-identity" in warnings[0]
