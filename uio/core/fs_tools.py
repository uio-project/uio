"""Read-only file tools: read a file, list files, search file contents.

An agent that should only read gets these instead of ``run_command``: nothing here can write,
run a program or reach the network. Every path is resolved (symbolic links included) and must
stay inside the root the run was given, which is the agent's working directory.

The outputs are capped so that one call cannot fill the model's context: a file is read a page at
a time, and a listing or a search stops at a fixed number of entries and says that it stopped.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

READ_DEFAULT_LINES = 2000
READ_MAX_CHARS = 100_000
LIST_MAX_ENTRIES = 500
SEARCH_MAX_MATCHES = 200
SEARCH_MAX_FILE_BYTES = 2_000_000
_LINE_MAX_CHARS = 2000

READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": (
        "Read a text file inside the working directory. Returns numbered lines, a page at a time: "
        f"{READ_DEFAULT_LINES} lines from `offset` (1-based) unless `limit` says otherwise."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The file, relative to the working directory.",
            },
            "offset": {"type": "integer", "description": "The first line to return, from 1."},
            "limit": {"type": "integer", "description": "How many lines to return."},
        },
        "required": ["path"],
    },
}

LIST_FILES_SCHEMA = {
    "name": "list_files",
    "description": (
        "List the files inside the working directory that match a glob pattern, such as `**/*.py` "
        f"or `docs/*.md`. At most {LIST_MAX_ENTRIES} paths, sorted."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "A glob pattern; `**` matches any depth."},
            "path": {
                "type": "string",
                "description": "A directory to search under (default: all).",
            },
        },
        "required": ["pattern"],
    },
}

SEARCH_FILES_SCHEMA = {
    "name": "search_files",
    "description": (
        "Search the text files inside the working directory for a regular expression (Python "
        f"syntax). Returns `path:line: text` for each match, at most {SEARCH_MAX_MATCHES}."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "A regular expression."},
            "path": {
                "type": "string",
                "description": "A file or directory to search (default: all).",
            },
            "glob": {
                "type": "string",
                "description": "Only search files whose path matches this glob.",
            },
            "ignore_case": {"type": "boolean", "description": "Match without regard to case."},
        },
        "required": ["pattern"],
    },
}

FS_TOOL_SCHEMAS = {s["name"]: s for s in (READ_FILE_SCHEMA, LIST_FILES_SCHEMA, SEARCH_FILES_SCHEMA)}


class OutsideRoot(ValueError):
    pass


def _resolve(root: Path, given: str | None) -> Path:
    """The path asked for, resolved, or an error if it leaves the root."""
    root = root.resolve()
    target = (root / (given or ".")).resolve()
    if target != root and root not in target.parents:
        raise OutsideRoot(f"{given!r} is outside the working directory")
    return target


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root.resolve()).as_posix()


def _is_text(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return b"\0" not in handle.read(8192)
    except OSError:
        return False


def _int(value, default: int, low: int) -> int:
    try:
        return max(low, int(value))
    except (TypeError, ValueError):
        return default


def read_file(root: Path, args: dict) -> str:
    path = _resolve(root, args.get("path"))
    if not path.is_file():
        return f"Error: {args.get('path')!r} is not a file"
    if not _is_text(path):
        return f"Error: {args.get('path')!r} is not a text file"
    offset = _int(args.get("offset"), 1, 1)
    limit = _int(args.get("limit"), READ_DEFAULT_LINES, 1)
    out: list[str] = []
    size, more, stopped = 0, False, False
    with path.open(encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle, 1):
            if number < offset:
                continue
            if number >= offset + limit:
                more = True
                break
            line = line.rstrip("\n")
            if len(line) > _LINE_MAX_CHARS:
                line = line[:_LINE_MAX_CHARS] + " […]"
            entry = f"{number:>6}\t{line}"
            if size + len(entry) > READ_MAX_CHARS:
                out.append(f"[stopped at {READ_MAX_CHARS} characters: read on from line {number}]")
                stopped = True
                break
            out.append(entry)
            size += len(entry) + 1
    if not out:
        return f"(the file has no line {offset})" if offset > 1 else "(the file is empty)"
    if more and not stopped:
        out.append(f"[more: read on from line {offset + limit}]")
    return "\n".join(out)


def _walk(root: Path, base: Path):
    """Every file under ``base``, sorted. A link that leads out of the root is left out."""
    top = root.resolve()
    for directory, subdirs, files in os.walk(base):
        subdirs.sort()
        for name in sorted(files):
            path = Path(directory) / name
            real = path.resolve()
            if real == top or top in real.parents:
                yield path


def list_files(root: Path, args: dict) -> str:
    pattern = args.get("pattern") or "**/*"
    base = _resolve(root, args.get("path"))
    if not base.is_dir():
        return f"Error: {args.get('path')!r} is not a directory"
    found = []
    for path in _walk(root, base):
        rel = _relative(root, path)
        if (
            fnmatch.fnmatch(rel, pattern)
            or fnmatch.fnmatch(_relative(base, path), pattern)
            or (pattern.startswith("**/") and fnmatch.fnmatch(path.name, pattern[3:]))
        ):
            found.append(rel)
            if len(found) == LIST_MAX_ENTRIES:
                found.append(f"[stopped at {LIST_MAX_ENTRIES} paths: narrow the pattern]")
                break
    return "\n".join(found) if found else "(no file matches)"


def search_files(root: Path, args: dict) -> str:
    try:
        regex = re.compile(
            args.get("pattern") or "", re.IGNORECASE if args.get("ignore_case") else 0
        )
    except re.error as exc:
        return f"Error: the pattern is not a valid regular expression: {exc}"
    base = _resolve(root, args.get("path"))
    glob = args.get("glob")
    files = [base] if base.is_file() else list(_walk(root, base)) if base.is_dir() else []
    if not files:
        return f"Error: {args.get('path')!r} does not exist"
    out = []
    for path in files:
        rel = _relative(root, path)
        if glob and not (fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(path.name, glob)):
            continue
        try:
            if path.stat().st_size > SEARCH_MAX_FILE_BYTES or not _is_text(path):
                continue
            with path.open(encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    if regex.search(line):
                        text = line.rstrip("\n")
                        if len(text) > 300:
                            text = text[:300] + " […]"
                        out.append(f"{rel}:{number}: {text}")
                        if len(out) == SEARCH_MAX_MATCHES:
                            out.append(
                                f"[stopped at {SEARCH_MAX_MATCHES} matches: narrow the search]"
                            )
                            return "\n".join(out)
        except OSError:
            continue
    return "\n".join(out) if out else "(no match)"


_HANDLERS = {"read_file": read_file, "list_files": list_files, "search_files": search_files}


def execute_fs_tool(name: str, args: dict, root: str | os.PathLike) -> str:
    """Run one of the read-only file tools. Errors come back as text for the model to read."""
    try:
        return _HANDLERS[name](Path(root), args or {})
    except OutsideRoot as exc:
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error: {exc.strerror or exc}"
