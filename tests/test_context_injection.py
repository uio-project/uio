"""Tests for context: frontmatter glob injection."""

from __future__ import annotations

import os

from uio.core.runner import _build_context_section, _count_tokens


class TestCountTokens:
    def test_empty_string(self):
        assert _count_tokens("") == 0

    def test_four_chars_is_one_token(self):
        assert _count_tokens("abcd") == 1

    def test_longer_text(self):
        assert _count_tokens("a" * 400) == 100


class TestBuildContextSection:
    def test_empty_globs_returns_empty(self, tmp_path):
        result = _build_context_section([], str(tmp_path), 8000)
        assert result == ""

    def test_nonmatching_glob_silently_skipped(self, tmp_path):
        result = _build_context_section(["does_not_exist.md"], str(tmp_path), 8000)
        assert result == ""

    def test_single_file_included(self, tmp_path):
        f = tmp_path / "README.md"
        f.write_text("Hello world")
        result = _build_context_section(["README.md"], str(tmp_path), 8000)
        assert "## Context" in result
        assert "README.md" in result
        assert "Hello world" in result

    def test_multiple_files_included(self, tmp_path):
        (tmp_path / "a.md").write_text("File A")
        (tmp_path / "b.md").write_text("File B")
        result = _build_context_section(["*.md"], str(tmp_path), 8000)
        assert "File A" in result
        assert "File B" in result

    def test_directory_entries_skipped(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = _build_context_section(["subdir"], str(tmp_path), 8000)
        assert result == ""

    def test_recursive_glob(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("Nested content")
        result = _build_context_section(["**/*.md"], str(tmp_path), 8000)
        assert "Nested content" in result

    def test_truncation_with_marker(self, tmp_path):
        # File has 400 tokens worth of content (~1600 chars), cap is 10 tokens
        content = "x" * 1600
        (tmp_path / "big.txt").write_text(content)
        result = _build_context_section(["big.txt"], str(tmp_path), max_tokens=10)
        assert "[truncated —" in result
        assert "tokens omitted]" in result
        # Should only include first 10*4=40 chars of content
        assert "x" * 40 in result
        assert "x" * 41 not in result

    def test_second_file_skipped_after_cap(self, tmp_path):
        big = "y" * 40000  # ~10000 tokens
        (tmp_path / "big.txt").write_text(big)
        (tmp_path / "small.txt").write_text("Should not appear")
        result = _build_context_section(["big.txt", "small.txt"], str(tmp_path), max_tokens=100)
        assert "Should not appear" not in result

    def test_string_glob_normalised_to_list(self, tmp_path):
        # runner.py normalises str -> [str] before calling _build_context_section,
        # but the function itself also accepts a list; test that directly.
        (tmp_path / "file.md").write_text("content here")
        result = _build_context_section(["file.md"], str(tmp_path), 8000)
        assert "content here" in result

    def test_context_heading_present(self, tmp_path):
        (tmp_path / "notes.md").write_text("some notes")
        result = _build_context_section(["notes.md"], str(tmp_path), 8000)
        assert result.startswith("## Context\n\n")

    def test_relative_path_in_heading(self, tmp_path):
        sub = tmp_path / "docs"
        sub.mkdir()
        (sub / "guide.md").write_text("guide content")
        result = _build_context_section(["docs/guide.md"], str(tmp_path), 8000)
        assert os.path.join("docs", "guide.md") in result

    def test_exact_budget_no_spurious_section(self, tmp_path):
        # First file exactly fills the budget; second file should produce no section at all.
        # 40 chars = 10 tokens; max_tokens=10 means first file exactly fills budget.
        (tmp_path / "a.txt").write_text("a" * 40)
        (tmp_path / "b.txt").write_text("should not appear")
        result = _build_context_section(["a.txt", "b.txt"], str(tmp_path), max_tokens=10)
        assert "a" * 40 in result
        assert "should not appear" not in result
        assert "[truncated" not in result

    def test_single_pattern_multi_file_cap(self, tmp_path):
        # Both files match a single glob pattern; cap is hit on the first file.
        (tmp_path / "a.txt").write_text("z" * 40000)  # ~10000 tokens
        (tmp_path / "b.txt").write_text("should not appear")
        result = _build_context_section(["*.txt"], str(tmp_path), max_tokens=100)
        assert "should not appear" not in result


class TestParserAcceptsContextKey:
    """Ensure validate_definition does not flag 'context' as unknown."""

    def test_context_key_is_known(self, tmp_path):
        from uio.schema.parser import validate_definition

        fm = {
            "name": "test-agent",
            "description": "A test.",
            "context": ["README.md"],
        }
        errors = validate_definition(str(tmp_path / "test.agent.md"), fm)
        assert not any("unrecognised" in e and "context" in e for e in errors)
