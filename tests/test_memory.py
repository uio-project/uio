"""Tests for the *.memory.md definition type and uio memory CLI."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from uio.cli.main import main
from uio.core.memory import (
    build_memory_section,
    clear_all_memory,
    clear_session_memory,
    estimate_tokens,
    load_memory_files,
    write_memory_body,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_memory(directory: Path, filename: str, name: str, scope: str, body: str) -> Path:
    path = directory / filename
    content = f"---\nname: {name}\ndescription: test\nscope: {scope}\n---\n{body}\n"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# load_memory_files
# ---------------------------------------------------------------------------


def test_load_memory_files_empty_dir(tmp_path):
    entries = load_memory_files(str(tmp_path))
    assert entries == []


def test_load_memory_files_nonexistent_dir(tmp_path):
    entries = load_memory_files(str(tmp_path / "nonexistent"))
    assert entries == []


def test_load_memory_files_reads_frontmatter_and_body(tmp_path):
    _write_memory(tmp_path, "ctx.memory.md", "ctx", "project", "Some context.")
    entries = load_memory_files(str(tmp_path))
    assert len(entries) == 1
    path, fm, body = entries[0]
    assert fm["name"] == "ctx"
    assert fm["scope"] == "project"
    assert body == "Some context."


def test_load_memory_files_ignores_non_memory_files(tmp_path):
    (tmp_path / "agent.agent.md").write_text("---\nname: A\ndescription: D.\n---\nBody.")
    entries = load_memory_files(str(tmp_path))
    assert entries == []


def test_load_memory_files_sorted_alphabetically(tmp_path):
    _write_memory(tmp_path, "z.memory.md", "z", "project", "Z body.")
    _write_memory(tmp_path, "a.memory.md", "a", "project", "A body.")
    entries = load_memory_files(str(tmp_path))
    names = [fm["name"] for _, fm, _ in entries]
    assert names == ["a", "z"]


# ---------------------------------------------------------------------------
# build_memory_section
# ---------------------------------------------------------------------------


def test_build_memory_section_empty_dir(tmp_path):
    assert build_memory_section(str(tmp_path)) == ""


def test_build_memory_section_single_entry(tmp_path):
    _write_memory(tmp_path, "ctx.memory.md", "ctx", "project", "Key fact.")
    section = build_memory_section(str(tmp_path))
    assert "## Persistent Memory" in section
    assert "### ctx" in section
    assert "Key fact." in section


def test_build_memory_section_skips_empty_bodies(tmp_path):
    _write_memory(tmp_path, "empty.memory.md", "empty", "project", "")
    assert build_memory_section(str(tmp_path)) == ""


def test_build_memory_section_multiple_entries_separated(tmp_path):
    _write_memory(tmp_path, "a.memory.md", "a", "project", "Body A.")
    _write_memory(tmp_path, "b.memory.md", "b", "session", "Body B.")
    section = build_memory_section(str(tmp_path))
    assert "### a" in section
    assert "### b" in section
    assert "---" in section


# ---------------------------------------------------------------------------
# clear_session_memory
# ---------------------------------------------------------------------------


def test_clear_session_memory_clears_session_scope(tmp_path):
    _write_memory(tmp_path, "sess.memory.md", "sess", "session", "Temporary data.")
    clear_session_memory(str(tmp_path))
    entries = load_memory_files(str(tmp_path))
    assert len(entries) == 1
    _, _, body = entries[0]
    assert body == ""


def test_clear_session_memory_preserves_project_scope(tmp_path):
    _write_memory(tmp_path, "proj.memory.md", "proj", "project", "Permanent data.")
    clear_session_memory(str(tmp_path))
    entries = load_memory_files(str(tmp_path))
    _, _, body = entries[0]
    assert body == "Permanent data."


def test_clear_session_memory_mixed_scopes(tmp_path):
    _write_memory(tmp_path, "a.memory.md", "a", "project", "Keep me.")
    _write_memory(tmp_path, "b.memory.md", "b", "session", "Erase me.")
    clear_session_memory(str(tmp_path))
    entries = {fm["name"]: body for _, fm, body in load_memory_files(str(tmp_path))}
    assert entries["a"] == "Keep me."
    assert entries["b"] == ""


# ---------------------------------------------------------------------------
# write_memory_body (YAML safety)
# ---------------------------------------------------------------------------


def test_write_memory_body_roundtrips_special_chars(tmp_path):
    """Frontmatter with colon-containing description must roundtrip safely."""
    path = str(tmp_path / "tricky.memory.md")
    fm = {"name": "tricky", "description": "Tracks goals: Q3", "scope": "project"}
    write_memory_body(path, fm, "Body text.")
    fm2, body2 = load_memory_files(str(tmp_path))[0][1:3]
    assert fm2["description"] == "Tracks goals: Q3"
    assert body2 == "Body text."


def test_write_memory_body_clears_body(tmp_path):
    path = str(tmp_path / "s.memory.md")
    fm = {"name": "s", "description": "d", "scope": "session"}
    write_memory_body(path, fm, "Initial body.")
    write_memory_body(path, fm, "")
    _, _, body = load_memory_files(str(tmp_path))[0]
    assert body == ""


# ---------------------------------------------------------------------------
# clear_all_memory
# ---------------------------------------------------------------------------


def test_clear_all_memory_clears_all_scopes(tmp_path):
    _write_memory(tmp_path, "a.memory.md", "a", "project", "Data A.")
    _write_memory(tmp_path, "b.memory.md", "b", "session", "Data B.")
    cleared = clear_all_memory(str(tmp_path))
    assert len(cleared) == 2
    entries = {fm["name"]: body for _, fm, body in load_memory_files(str(tmp_path))}
    assert entries["a"] == ""
    assert entries["b"] == ""


def test_clear_all_memory_skips_already_empty(tmp_path):
    _write_memory(tmp_path, "empty.memory.md", "empty", "project", "")
    cleared = clear_all_memory(str(tmp_path))
    assert cleared == []


# ---------------------------------------------------------------------------
# clear_session_memory (return value)
# ---------------------------------------------------------------------------


def test_clear_session_memory_returns_cleared(tmp_path):
    _write_memory(tmp_path, "s.memory.md", "s", "session", "Data.")
    cleared = clear_session_memory(str(tmp_path))
    assert cleared == [("s", "session")]


def test_clear_session_memory_returns_empty_when_nothing_to_clear(tmp_path):
    _write_memory(tmp_path, "p.memory.md", "p", "project", "Data.")
    cleared = clear_session_memory(str(tmp_path))
    assert cleared == []


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


def test_estimate_tokens_basic():
    assert estimate_tokens("a" * 400) == 100


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


# ---------------------------------------------------------------------------
# CLI: uio memory list
# ---------------------------------------------------------------------------


@pytest.fixture()
def memory_dir(tmp_path, monkeypatch):
    mem = tmp_path / "memory"
    mem.mkdir()
    monkeypatch.chdir(tmp_path)
    (tmp_path / "uio.toml").write_text(
        textwrap.dedent(f"""\
        [dirs]
        memory = "{mem}"
        agents = "{tmp_path / "agents"}"
        skills = "{tmp_path / "skills"}"
        prompts = "{tmp_path / "prompts"}"
        """)
    )
    return mem


def test_memory_list_empty(memory_dir):
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "list"])
    assert result.exit_code == 0
    assert "No memory files found" in result.output


def test_memory_list_shows_entries(memory_dir):
    _write_memory(memory_dir, "ctx.memory.md", "ctx", "project", "Some data here.")
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "list"])
    assert result.exit_code == 0
    assert "ctx" in result.output
    assert "project" in result.output


# ---------------------------------------------------------------------------
# CLI: uio memory view
# ---------------------------------------------------------------------------


def test_memory_view_existing(memory_dir):
    _write_memory(memory_dir, "ctx.memory.md", "ctx", "project", "Detailed context.")
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "view", "ctx"])
    assert result.exit_code == 0
    assert "Detailed context." in result.output


def test_memory_view_missing(memory_dir):
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "view", "nonexistent"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI: uio memory clear
# ---------------------------------------------------------------------------


def test_memory_clear_all(memory_dir):
    _write_memory(memory_dir, "a.memory.md", "a", "project", "Data A.")
    _write_memory(memory_dir, "b.memory.md", "b", "session", "Data B.")
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "clear"])
    assert result.exit_code == 0
    entries = {fm["name"]: body for _, fm, body in load_memory_files(str(memory_dir))}
    assert entries["a"] == ""
    assert entries["b"] == ""


def test_memory_clear_session_only(memory_dir):
    _write_memory(memory_dir, "a.memory.md", "a", "project", "Keep me.")
    _write_memory(memory_dir, "b.memory.md", "b", "session", "Erase me.")
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "clear", "--session"])
    assert result.exit_code == 0
    entries = {fm["name"]: body for _, fm, body in load_memory_files(str(memory_dir))}
    assert entries["a"] == "Keep me."
    assert entries["b"] == ""


def test_memory_clear_nothing_to_clear(memory_dir):
    _write_memory(memory_dir, "empty.memory.md", "empty", "project", "")
    runner = CliRunner()
    result = runner.invoke(main, ["memory", "clear"])
    assert result.exit_code == 0
    assert "Nothing to clear" in result.output
