"""Structural validation tests for agent definitions in definitions/agents/.

Mirrors the parametrized approach used by test_examples.py for embedded EXAMPLES,
but discovers files on disk so new definitions are picked up automatically.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from uio.schema.parser import parse_definition_file, validate_definition

_AGENTS_DIR = pathlib.Path(__file__).parent.parent / "definitions" / "agents"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def _all_agent_files() -> list[pathlib.Path]:
    return sorted(_AGENTS_DIR.glob("**/*.agent.md"))


def _parse_frontmatter(path: pathlib.Path) -> tuple[dict, str]:
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content.strip()
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


def test_agents_dir_has_definitions():
    files = _all_agent_files()
    assert files, f"No .agent.md files found under {_AGENTS_DIR}"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_frontmatter(path):
    fm, _ = _parse_frontmatter(path)
    assert fm, f"{path.name}: no frontmatter found"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_name(path):
    fm, _ = _parse_frontmatter(path)
    assert fm.get("name"), f"{path.name}: missing 'name' field"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_description(path):
    fm, _ = _parse_frontmatter(path)
    assert fm.get("description"), f"{path.name}: missing 'description' field"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_has_nonempty_body(path):
    _, body = _parse_frontmatter(path)
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
    fm, _ = _parse_frontmatter(path)
    complexity = fm.get("complexity")
    if complexity is not None:
        assert complexity in {"large", "small"}, f"{path.name}: invalid complexity '{complexity}'"


@pytest.mark.parametrize("path", _all_agent_files(), ids=lambda p: p.name)
def test_definition_capabilities_are_known(path, tmp_path):
    dest = tmp_path / path.name
    dest.write_text(path.read_text())
    fm, _ = parse_definition_file(str(dest))
    errors = validate_definition(str(dest), fm)
    capability_errors = [e for e in errors if "capability" in e]
    assert capability_errors == [], f"{path.name}: unknown capabilities: {capability_errors}"
