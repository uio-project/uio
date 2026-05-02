"""Memory file loading, injection, and session cleanup for *.memory.md files."""

from __future__ import annotations

import re
from glob import glob
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)

VALID_SCOPES = ("project", "session")


def _parse_memory_file(path: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) for a memory file."""
    with open(path) as f:
        raw = f.read()
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw.strip()
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


def _write_memory_body(path: str, frontmatter: dict, body: str) -> None:
    """Rewrite a memory file with the given body (preserves frontmatter)."""
    lines = ["---"]
    for key, value in frontmatter.items():
        if isinstance(value, str):
            lines.append(f"{key}: {value!r}" if "\n" in value else f"{key}: {value}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    if body:
        lines.append(body)
    Path(path).write_text("\n".join(lines) + "\n")


def load_memory_files(memory_dir: str) -> list[tuple[str, dict, str]]:
    """Return (path, frontmatter, body) for all *.memory.md files in memory_dir."""
    pattern = f"{memory_dir}/*.memory.md"
    results = []
    for path in sorted(glob(pattern)):
        try:
            fm, body = _parse_memory_file(path)
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


def clear_session_memory(memory_dir: str) -> None:
    """Truncate the body of all session-scoped memory files to empty."""
    for path, fm, _body in load_memory_files(memory_dir):
        if fm.get("scope") == "session":
            _write_memory_body(path, fm, "")


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 4 characters per token."""
    return max(1, len(text) // 4)
