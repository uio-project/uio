"""YAML frontmatter parser for .agent.md, .skill.md, and .prompt.md files."""
from __future__ import annotations

import re

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)

REQUIRED_FIELDS = ("name", "description")


def parse_definition_file(path: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) for a definition file."""
    with open(path) as f:
        raw = f.read()
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw.strip()
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


def validate_definition(path: str, frontmatter: dict) -> list[str]:
    """Return a list of error/warning strings. Empty list means valid."""
    errors = []
    for field in REQUIRED_FIELDS:
        if not frontmatter.get(field):
            errors.append(f"{path}: missing required field '{field}'")
    known = {"name", "description", "complexity", "tools", "timeout", "argument-hint", "invokable"}
    for key in frontmatter:
        if key not in known:
            errors.append(f"{path}: unrecognised frontmatter key '{key}'")
    return errors
