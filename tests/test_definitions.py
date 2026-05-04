"""Structural validation tests for agent definitions in definitions/agents/.

Mirrors the parametrized approach used by test_examples.py for embedded EXAMPLES,
but discovers files on disk so new definitions are picked up automatically.
"""

from __future__ import annotations

import pathlib

import pytest

from uio.schema.parser import parse_definition_file, validate_definition

_AGENTS_DIR = pathlib.Path(__file__).parent.parent / "definitions" / "agents"


def _all_agent_files() -> list[pathlib.Path]:
    return sorted(_AGENTS_DIR.glob("**/*.agent.md"))


def test_agents_dir_has_definitions():
    files = _all_agent_files()
    assert files, f"No .agent.md files found under {_AGENTS_DIR}"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_frontmatter(path):
    fm, _ = parse_definition_file(str(path))
    assert fm, f"{path.name}: no frontmatter found"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_name(path):
    fm, _ = parse_definition_file(str(path))
    assert fm.get("name"), f"{path.name}: missing 'name' field"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_description(path):
    fm, _ = parse_definition_file(str(path))
    assert fm.get("description"), f"{path.name}: missing 'description' field"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_nonempty_body(path):
    _, body = parse_definition_file(str(path))
    assert body.strip(), f"{path.name}: body is empty"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_passes_validation(path, tmp_path):
    dest = tmp_path / path.name
    dest.write_text(path.read_text())
    fm, _ = parse_definition_file(str(dest))
    errors = validate_definition(str(dest), fm)
    assert errors == [], f"{path.name}: validation errors: {errors}"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_complexity_is_valid(path):
    fm, _ = parse_definition_file(str(path))
    complexity = fm.get("complexity")
    if complexity is not None:
        assert complexity in {"large", "small"}, f"{path.name}: invalid complexity '{complexity}'"


# Distinct from test_definition_passes_validation: this test targets capability
# validation specifically and produces a focused error message when a definition
# introduces an unknown capability string, making failures easier to diagnose.
@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_capabilities_are_known(path, tmp_path):
    dest = tmp_path / path.name
    dest.write_text(path.read_text())
    fm, _ = parse_definition_file(str(dest))
    errors = validate_definition(str(dest), fm)
    capability_errors = [e for e in errors if "capability" in e]
    assert capability_errors == [], f"{path.name}: unknown capabilities: {capability_errors}"
