"""Tests for the YAML frontmatter parser."""

import textwrap


from uio.schema.parser import (
    check_identity_env,
    check_skill_references,
    parse_definition_file,
    validate_definition,
)


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


# ---------------------------------------------------------------------------
# check_skill_references
# ---------------------------------------------------------------------------


def test_check_skill_references_no_skills_dir(tmp_path):
    """Returns no warnings when skills directory does not exist."""
    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\n---\nRun /missing-skill to do the thing.")
    warnings = check_skill_references(
        str(f), "Run /missing-skill to do the thing.", str(tmp_path / "nonexistent")
    )
    assert warnings == []


def test_check_skill_references_empty_skills_dir(tmp_path):
    """Returns no warnings when the skills directory exists but is empty."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    warnings = check_skill_references("agent.agent.md", "Run /missing-skill here.", str(skills_dir))
    assert warnings == []


def test_check_skill_references_known_skill_no_warning(tmp_path):
    """No warning when the referenced skill exists on disk."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "my-skill.skill.md").write_text(
        "---\nname: my-skill\ndescription: D.\n---\nBody."
    )
    warnings = check_skill_references("agent.agent.md", "Run /my-skill with args.", str(skills_dir))
    assert warnings == []


def test_check_skill_references_unknown_skill_warns(tmp_path):
    """Warning when a standalone /skill-name token is not found in the skills directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "real-skill.skill.md").write_text(
        "---\nname: real-skill\ndescription: D.\n---\nBody."
    )
    warnings = check_skill_references(
        "agent.agent.md", "Run /ghost-skill to do the thing.", str(skills_dir)
    )
    assert len(warnings) == 1
    assert "ghost-skill" in warnings[0]


def test_check_skill_references_ignores_url_path_segments(tmp_path):
    """Path segments inside URLs should not produce warnings."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "real-skill.skill.md").write_text(
        "---\nname: real-skill\ndescription: D.\n---\nBody."
    )
    body = "See https://github.com/jomkz/uio/contents/foo for details."
    warnings = check_skill_references("agent.agent.md", body, str(skills_dir))
    assert warnings == []


def test_check_skill_references_ignores_deep_paths(tmp_path):
    """Filesystem paths like /tmp/foo should not match because /foo is preceded by /."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "real-skill.skill.md").write_text(
        "---\nname: real-skill\ndescription: D.\n---\nBody."
    )
    body = "Clone to /tmp/uio-coder-workspace and run /real-skill after."
    warnings = check_skill_references("agent.agent.md", body, str(skills_dir))
    # /tmp/uio-coder-workspace: /tmp is followed by /, so no match; /uio-coder-workspace is preceded by /
    # /real-skill: known skill, no warning
    assert warnings == []


def test_check_skill_references_ignores_numeric_segments(tmp_path):
    """/42, /123 etc. start with digits and must not be matched."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "real-skill.skill.md").write_text(
        "---\nname: real-skill\ndescription: D.\n---\nBody."
    )
    body = "See issue /42 and PR /123 for context."
    warnings = check_skill_references("agent.agent.md", body, str(skills_dir))
    assert warnings == []


def test_validate_unknown_capability_warns(tmp_path):
    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\ncapabilities:\n  - vcs\n  - notareal\n---\nBody.")
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert any("notareal" in e for e in errors)


def test_validate_known_capabilities_accepted(tmp_path):
    f = tmp_path / "agent.agent.md"
    f.write_text(
        "---\nname: A\ndescription: D.\ncapabilities:\n  - vcs\n  - git\n  - ci\n---\nBody."
    )
    fm, _ = parse_definition_file(str(f))
    errors = validate_definition(str(f), fm)
    assert not any("capability" in e for e in errors)


def test_validate_no_vcs_identity_does_not_import_github_app(tmp_path):
    """validate_definition on a definition with no vcs-identity must not load github_app."""
    import sys

    sys.modules.pop("uio.providers.github.app", None)
    f = tmp_path / "test.agent.md"
    f.write_text("---\nname: test\ndescription: test\n---\n# Agent: test\n")
    fm, _ = parse_definition_file(str(f))
    validate_definition(str(f), fm)
    assert "uio.providers.github.app" not in sys.modules


# ---------------------------------------------------------------------------
# check_skill_references — code block false-positive prevention (issue #189)
# ---------------------------------------------------------------------------


def _make_skills_dir(tmp_path, *skill_names):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(exist_ok=True)
    for name in skill_names:
        (skills_dir / f"{name}.skill.md").write_text(
            f"---\nname: {name}\ndescription: D.\n---\nBody."
        )
    return str(skills_dir)


def test_check_skill_references_fenced_block_no_false_positive(tmp_path):
    """A /word inside a fenced code block must not produce a warning."""
    skills_dir = _make_skills_dir(tmp_path, "real-skill")
    body = "Before.\n\n```\n/exit\n/nonexistent-skill\n```\n\nAfter."
    warnings = check_skill_references("agent.agent.md", body, skills_dir)
    assert warnings == []


def test_check_skill_references_inline_code_no_false_positive(tmp_path):
    """A /word inside an inline code span must not produce a warning."""
    skills_dir = _make_skills_dir(tmp_path, "real-skill")
    body = "Call `/ghost-skill` to do the thing."
    warnings = check_skill_references("agent.agent.md", body, skills_dir)
    assert warnings == []


def test_check_skill_references_outside_code_block_still_detected(tmp_path):
    """A /word outside any code block continues to trigger a warning."""
    skills_dir = _make_skills_dir(tmp_path, "real-skill")
    body = "Run /ghost-skill here.\n\n```\n/also-ghost\n```"
    warnings = check_skill_references("agent.agent.md", body, skills_dir)
    assert len(warnings) == 1
    assert "ghost-skill" in warnings[0]


def test_check_skill_references_known_skill_in_code_block_no_warning(tmp_path):
    """A known skill referenced only inside a code block is not flagged."""
    skills_dir = _make_skills_dir(tmp_path, "real-skill")
    body = "Example:\n\n```\n/real-skill with args\n```"
    warnings = check_skill_references("agent.agent.md", body, skills_dir)
    assert warnings == []
