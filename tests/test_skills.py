"""Structural validation tests for skill definitions in definitions/skills/."""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from uio.schema.parser import parse_definition_file, validate_definition

_SKILLS_DIR = pathlib.Path(__file__).parent.parent / "definitions" / "skills"
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def _all_skill_files() -> list[pathlib.Path]:
    return sorted(_SKILLS_DIR.glob("**/*.skill.md"))


def _parse_frontmatter(path: pathlib.Path) -> tuple[dict, str]:
    content = path.read_text()
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content.strip()
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


def test_skills_dir_has_definitions():
    files = _all_skill_files()
    assert files, f"No .skill.md files found under {_SKILLS_DIR}"


@pytest.mark.parametrize("path", _all_skill_files(), ids=lambda p: p.name)
def test_skill_has_frontmatter(path):
    fm, _ = _parse_frontmatter(path)
    assert fm, f"{path.name}: no frontmatter found"


@pytest.mark.parametrize("path", _all_skill_files(), ids=lambda p: p.name)
def test_skill_has_name(path):
    fm, _ = _parse_frontmatter(path)
    assert fm.get("name"), f"{path.name}: missing 'name' field"


@pytest.mark.parametrize("path", _all_skill_files(), ids=lambda p: p.name)
def test_skill_has_description(path):
    fm, _ = _parse_frontmatter(path)
    assert fm.get("description"), f"{path.name}: missing 'description' field"


@pytest.mark.parametrize("path", _all_skill_files(), ids=lambda p: p.name)
def test_skill_has_nonempty_body(path):
    _, body = _parse_frontmatter(path)
    assert body.strip(), f"{path.name}: body is empty"


@pytest.mark.parametrize("path", _all_skill_files(), ids=lambda p: p.name)
def test_skill_passes_validation(path, tmp_path):
    dest = tmp_path / path.name
    dest.write_text(path.read_text())
    fm, _ = parse_definition_file(str(dest))
    errors = validate_definition(str(dest), fm)
    assert errors == [], f"{path.name}: validation errors: {errors}"


@pytest.mark.parametrize("path", _all_skill_files(), ids=lambda p: p.name)
def test_skill_has_steps_section(path):
    _, body = _parse_frontmatter(path)
    assert "## Steps" in body, f"{path.name}: missing '## Steps' section"
