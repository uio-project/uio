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
    known = {
        "name",
        "description",
        "complexity",
        "tools",
        "timeout",
        "argument-hint",
        "invokable",
        "github-identity",
    }
    for key in frontmatter:
        if key not in known:
            errors.append(f"{path}: unrecognised frontmatter key '{key}'")

    identity = frontmatter.get("github-identity")
    if identity is not None:
        from uio.core.github_app import KNOWN_ROLES

        if identity not in KNOWN_ROLES:
            errors.append(
                f"{path}: invalid 'github-identity' value '{identity}'"
                f" — must be one of {sorted(KNOWN_ROLES)}"
            )

    return errors


def check_identity_env(path: str, frontmatter: dict) -> list[str]:
    """Return warning strings when github-identity is declared but env vars are absent.

    Non-fatal — the agent can still run using the fallback credential.
    """
    from uio.core.github_app import KNOWN_ROLES, env_vars_present

    identity = frontmatter.get("github-identity")
    if not identity or identity not in KNOWN_ROLES:
        return []

    if not env_vars_present(identity):
        role_upper = identity.upper()
        prefix = f"GITHUB_APP_{role_upper}_"
        missing = [f"{prefix}{s}" for s in ("ID", "INSTALLATION_ID", "PRIVATE_KEY")]
        return [
            f"{path}: 'github-identity: {identity}' declared but env vars not set: "
            + ", ".join(missing)
        ]
    return []
