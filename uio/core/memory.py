"""Memory file loading, injection, and session cleanup for *.memory.md files."""

from __future__ import annotations

from glob import glob
from pathlib import Path

import yaml

from uio.schema.parser import parse_frontmatter_raw


def write_memory_body(path: str, frontmatter: dict, body: str) -> None:
    """Rewrite a memory file with the given body (preserves frontmatter)."""
    fm_text = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True).rstrip()
    content = f"---\n{fm_text}\n---\n"
    if body:
        content += body + "\n"
    Path(path).write_text(content)


def load_memory_files(memory_dir: str) -> list[tuple[str, dict, str]]:
    """Return (path, frontmatter, body) for all *.memory.md files in memory_dir."""
    pattern = f"{memory_dir}/*.memory.md"
    results = []
    for path in sorted(glob(pattern)):
        try:
            fm, body = parse_frontmatter_raw(path)
        except Exception:
            continue
        results.append((path, fm, body))
    return results


def build_memory_section(memory_dir: str) -> str:
    """Return a ``## Persistent Memory`` block for injection into the system prompt.

    Returns an empty string when no memory files exist or all are empty.
    """
    entries = load_memory_files(memory_dir)
    parts = []
    for _path, fm, body in entries:
        if not body:
            continue
        name = fm.get("name", Path(_path).stem)
        parts.append(f"### {name}\n\n{body}")
    if not parts:
        return ""
    return "## Persistent Memory\n\n" + "\n\n---\n\n".join(parts) + "\n\n"


def clear_session_memory(memory_dir: str) -> list[tuple[str, str]]:
    """Truncate the body of all session-scoped memory files to empty.

    Returns list of (name, scope) for entries that were cleared.
    """
    cleared = []
    for path, fm, _body in load_memory_files(memory_dir):
        if fm.get("scope") == "session":
            write_memory_body(path, fm, "")
            cleared.append((fm.get("name", Path(path).stem), "session"))
    return cleared


def clear_all_memory(memory_dir: str) -> list[tuple[str, str]]:
    """Truncate the body of all memory files. Returns list of (name, scope) cleared."""
    cleared = []
    for path, fm, body in load_memory_files(memory_dir):
        if body:
            write_memory_body(path, fm, "")
            cleared.append((fm.get("name", Path(path).stem), fm.get("scope", "project")))
    return cleared


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 4 characters per token."""
    return len(text) // 4
