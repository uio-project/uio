"""The read-only file tools, and the dispatch that keeps an agent to the tools it was offered."""

from __future__ import annotations

import os

import pytest

from uio.core import fs_tools
from uio.core.fs_tools import execute_fs_tool
from uio.core.tools import ToolCall, execute_tool


@pytest.fixture
def root(tmp_path):
    work = tmp_path / "work"
    (work / "src" / "pkg").mkdir(parents=True)
    (work / "docs").mkdir()
    (work / "src" / "pkg" / "a.py").write_text("import os\n\ndef alpha():\n    return 1\n")
    (work / "src" / "pkg" / "b.py").write_text("def beta():\n    return ALPHA\n")
    (work / "docs" / "guide.md").write_text("# Guide\n\nCall alpha() first.\n")
    (work / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0\0binary")
    (tmp_path / "secret.txt").write_text("outside the root\n")
    return work


def run(name: str, root, **args) -> str:
    return execute_fs_tool(name, args, root)


# ── read_file ──────────────────────────────────────────────────────────────────


def test_read_file_numbers_its_lines(root):
    assert run("read_file", root, path="src/pkg/a.py").splitlines() == [
        "     1\timport os",
        "     2\t",
        "     3\tdef alpha():",
        "     4\t    return 1",
    ]


def test_read_file_pages_with_offset_and_limit(root):
    out = run("read_file", root, path="src/pkg/a.py", offset=2, limit=2)
    assert out.splitlines() == ["     2\t", "     3\tdef alpha():", "[more: read on from line 4]"]
    assert run("read_file", root, path="src/pkg/a.py", offset=99) == "(the file has no line 99)"


def test_read_file_stops_at_its_character_cap(root, monkeypatch):
    monkeypatch.setattr(fs_tools, "READ_MAX_CHARS", 30)
    out = run("read_file", root, path="src/pkg/a.py")
    assert out.splitlines()[-1].startswith("[stopped at 30 characters: read on from line")


def test_read_file_cuts_a_very_long_line(root):
    (root / "long.txt").write_text("x" * 5000 + "\n")
    line = run("read_file", root, path="long.txt")
    assert line.endswith(" […]") and len(line) < 2100


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("missing.py", "is not a file"),
        ("src", "is not a file"),
        ("logo.png", "is not a text file"),
        ("../secret.txt", "outside the working directory"),
        ("/etc/hostname", "outside the working directory"),
    ],
)
def test_read_file_refuses_what_it_may_not_read(root, path, message):
    assert message in run("read_file", root, path=path)


def test_a_link_that_leads_out_of_the_root_is_not_followed(root):
    os.symlink(root.parent / "secret.txt", root / "link.txt")
    assert "outside the working directory" in run("read_file", root, path="link.txt")
    assert "link.txt" not in run("list_files", root, pattern="**/*")
    assert run("search_files", root, pattern="outside the root") == "(no match)"


# ── list_files ─────────────────────────────────────────────────────────────────


def test_list_files_matches_any_depth_with_a_double_star(root):
    assert run("list_files", root, pattern="**/*.py").splitlines() == [
        "src/pkg/a.py",
        "src/pkg/b.py",
    ]


def test_list_files_under_a_directory(root):
    assert run("list_files", root, pattern="*.md", path="docs") == "docs/guide.md"
    assert run("list_files", root, pattern="*.rs") == "(no file matches)"
    assert "outside the working directory" in run("list_files", root, pattern="*", path="..")


def test_list_files_stops_at_its_cap(root, monkeypatch):
    monkeypatch.setattr(fs_tools, "LIST_MAX_ENTRIES", 2)
    lines = run("list_files", root, pattern="**/*").splitlines()
    assert len(lines) == 3 and lines[-1].startswith("[stopped at 2 paths")


# ── search_files ───────────────────────────────────────────────────────────────


def test_search_files_finds_each_matching_line(root):
    assert run("search_files", root, pattern=r"alpha\(").splitlines() == [
        "docs/guide.md:3: Call alpha() first.",
        "src/pkg/a.py:3: def alpha():",
    ]


def test_search_files_by_case_and_by_glob(root):
    assert run(
        "search_files", root, pattern="alpha", ignore_case=True, glob="*.py"
    ).splitlines() == [
        "src/pkg/a.py:3: def alpha():",
        "src/pkg/b.py:2:     return ALPHA",
    ]
    assert (
        run("search_files", root, pattern="alpha", path="docs/guide.md")
        == "docs/guide.md:3: Call alpha() first."
    )


def test_search_files_skips_binary_files_and_says_when_nothing_matched(root):
    assert run("search_files", root, pattern="PNG") == "(no match)"


def test_search_files_refuses_a_bad_pattern_and_stops_at_its_cap(root, monkeypatch):
    assert "not a valid regular expression" in run("search_files", root, pattern="(")
    monkeypatch.setattr(fs_tools, "SEARCH_MAX_MATCHES", 1)
    out = run("search_files", root, pattern="return").splitlines()
    assert len(out) == 2 and out[-1].startswith("[stopped at 1 matches")


# ── execute_tool: only the tools a run was offered ─────────────────────────────


def test_a_file_tool_runs_inside_the_given_root(root):
    tc = ToolCall(name="read_file", args={"path": "docs/guide.md"}, call_id="1")
    out = execute_tool(tc, allowed=("read_file",), fs_root=str(root))
    assert "Call alpha() first." in out


def test_the_shell_is_refused_when_it_was_not_offered(root):
    tc = ToolCall(name="run_command", args={"command": "echo hi"}, call_id="1")
    assert execute_tool(tc, allowed=("read_file",), fs_root=str(root)) == (
        "Error: the tool 'run_command' is not available in this run"
    )


def test_file_tools_are_refused_by_default(root):
    tc = ToolCall(name="read_file", args={"path": "docs/guide.md"}, call_id="1")
    assert "is not available in this run" in execute_tool(tc, fs_root=str(root))
