"""Tests for bundled example definitions in uio.examples."""
import pytest

from uio.examples import EXAMPLES
from uio.schema.parser import parse_definition_file, validate_definition
import io
import re
import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)


def _parse_embedded(content: str) -> tuple[dict, str]:
    """Parse frontmatter from an embedded definition string."""
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return {}, content.strip()
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


# ── Structure ─────────────────────────────────────────────────────────────────

def test_examples_has_agents_key():
    assert "agents" in EXAMPLES


def test_examples_has_skills_key():
    assert "skills" in EXAMPLES


def test_examples_has_prompts_key():
    assert "prompts" in EXAMPLES


def test_examples_nonempty():
    total = sum(len(v) for v in EXAMPLES.values())
    assert total >= 4, f"Expected at least 4 bundled examples, got {total}"


# ── Filename conventions ──────────────────────────────────────────────────────

def test_agent_filenames_end_with_agent_md():
    for filename, _ in EXAMPLES["agents"]:
        assert filename.endswith(".agent.md"), f"Bad agent filename: {filename}"


def test_skill_filenames_end_with_skill_md():
    for filename, _ in EXAMPLES["skills"]:
        assert filename.endswith(".skill.md"), f"Bad skill filename: {filename}"


def test_prompt_filenames_end_with_prompt_md():
    for filename, _ in EXAMPLES["prompts"]:
        assert filename.endswith(".prompt.md"), f"Bad prompt filename: {filename}"


# ── Frontmatter parsing ───────────────────────────────────────────────────────

def _all_examples():
    for kind, entries in EXAMPLES.items():
        for filename, content in entries:
            yield filename, content


@pytest.mark.parametrize("filename,content", list(_all_examples()))
def test_example_has_frontmatter(filename, content):
    fm, _ = _parse_embedded(content)
    assert fm, f"{filename}: no frontmatter found"


@pytest.mark.parametrize("filename,content", list(_all_examples()))
def test_example_has_name(filename, content):
    fm, _ = _parse_embedded(content)
    assert fm.get("name"), f"{filename}: missing 'name' field"


@pytest.mark.parametrize("filename,content", list(_all_examples()))
def test_example_has_description(filename, content):
    fm, _ = _parse_embedded(content)
    assert fm.get("description"), f"{filename}: missing 'description' field"


@pytest.mark.parametrize("filename,content", list(_all_examples()))
def test_example_has_nonempty_body(filename, content):
    _, body = _parse_embedded(content)
    assert body.strip(), f"{filename}: body is empty"


# ── Validate via schema.parser ────────────────────────────────────────────────

@pytest.mark.parametrize("filename,content", list(_all_examples()))
def test_example_passes_validation(filename, content, tmp_path):
    """Write each example to a temp file and validate through the real parser."""
    dest = tmp_path / filename
    dest.write_text(content)
    fm, _ = parse_definition_file(str(dest))
    errors = validate_definition(str(dest), fm)
    assert errors == [], f"{filename}: validation errors: {errors}"


# ── Agent-specific ────────────────────────────────────────────────────────────

def test_agent_complexity_is_valid():
    valid = {"large", "small"}
    for filename, content in EXAMPLES["agents"]:
        fm, _ = _parse_embedded(content)
        complexity = fm.get("complexity")
        if complexity is not None:
            assert complexity in valid, f"{filename}: invalid complexity '{complexity}'"


# ── Prompt-specific ───────────────────────────────────────────────────────────

def test_prompts_are_invokable():
    for filename, content in EXAMPLES["prompts"]:
        fm, _ = _parse_embedded(content)
        assert fm.get("invokable") is True, f"{filename}: expected invokable: true"


# ── No duplicate filenames ────────────────────────────────────────────────────

def test_no_duplicate_filenames():
    seen: set[str] = set()
    for _, entries in EXAMPLES.items():
        for filename, _ in entries:
            assert filename not in seen, f"Duplicate example filename: {filename}"
            seen.add(filename)
