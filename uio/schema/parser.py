"""YAML frontmatter parser for .agent.md, .skill.md, and .prompt.md files."""

from __future__ import annotations

import os
import re

import yaml

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)

REQUIRED_FIELDS = ("name", "description")

# Matches "# <Type>: <name>" H1 headings
_H1_RE = re.compile(r"^#\s+(\w+):\s+(.+)$", re.MULTILINE)

# Stopping-criteria phrases expected somewhere in agent bodies
_STOPPING_PHRASES = re.compile(
    r"(stop\b|stopping criteria|do not proceed|halt|report and stop|print.*and stop)",
    re.IGNORECASE,
)


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
        "capabilities",
        "timeout",
        "argument-hint",
        "invokable",
        "max_tokens",
        "guardrails",
        "github-identity",  # deprecated alias for vcs-identity
        "vcs-identity",
        "vcs-provider",
    }
    for key in frontmatter:
        if key not in known:
            errors.append(f"{path}: unrecognised frontmatter key '{key}'")

    # vcs-identity validation
    vcs_identity = frontmatter.get("vcs-identity")
    if vcs_identity is not None:
        from uio.core.github_app import KNOWN_ROLES

        if vcs_identity not in KNOWN_ROLES:
            errors.append(
                f"{path}: invalid 'vcs-identity' value '{vcs_identity}'"
                f" — must be one of {sorted(KNOWN_ROLES)}"
            )

    # github-identity is the deprecated predecessor of vcs-identity
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
    """Return warning strings when a VCS identity is declared but env vars are absent.

    Non-fatal — the agent can still run using the fallback credential.
    Checks ``vcs-identity`` first, then the deprecated ``github-identity``.
    """
    from uio.core.github_app import KNOWN_ROLES, env_vars_present

    identity = frontmatter.get("vcs-identity") or frontmatter.get("github-identity")
    if not identity or identity not in KNOWN_ROLES:
        return []

    provider = frontmatter.get("vcs-provider", "github")
    if provider != "github":
        # Non-GitHub providers use different env vars; skip this check for now.
        return []

    if not env_vars_present(identity):
        role_upper = identity.upper()
        prefix = f"GITHUB_APP_{role_upper}_"
        missing = [f"{prefix}{s}" for s in ("ID", "INSTALLATION_ID", "PRIVATE_KEY")]
        field = "vcs-identity" if frontmatter.get("vcs-identity") else "github-identity"
        return [
            f"{path}: '{field}: {identity}' declared but env vars not set: " + ", ".join(missing)
        ]
    return []


def check_heading_format(path: str, frontmatter: dict, body: str) -> list[str]:
    """Warn when the first H1 heading does not match ``# {Type}: {name}``.

    The ``name`` in the heading must match the ``name`` frontmatter field.
    Non-fatal — different heading styles are allowed but flagged.
    """
    warnings: list[str] = []
    name = frontmatter.get("name")
    if not name:
        return warnings  # already caught by validate_definition

    m = _H1_RE.search(body)
    if m is None:
        warnings.append(f"{path}: no H1 heading found; expected '# <Type>: {name}'")
        return warnings

    heading_name = m.group(2).strip()
    if heading_name != name:
        warnings.append(
            f"{path}: H1 heading name '{heading_name}' does not match frontmatter name '{name}'"
        )
    return warnings


def check_skill_references(path: str, body: str, skills_dir: str) -> list[str]:
    """Warn when the body references skills that do not exist on disk.

    Detects invocation patterns like ``/skill-name`` or ``invoke.*skill-name``
    and resolves them against ``*.skill.md`` files in *skills_dir*.
    """
    warnings: list[str] = []
    # Collect known skill names from the skills directory
    known: set[str] = set()
    if os.path.isdir(skills_dir):
        for fname in os.listdir(skills_dir):
            if fname.endswith(".skill.md"):
                known.add(fname[: -len(".skill.md")])

    if not known:
        return warnings  # no skills directory or no skills — nothing to validate against

    # Match /skill-name invocations: only standalone tokens preceded by whitespace or
    # start-of-string. The lookahead (?![a-zA-Z0-9_/-]) requires the token to end at a
    # non-word, non-slash boundary, which also prevents regex backtracking from
    # producing spurious short matches inside path segments like /tmp/foo.
    invocations = re.findall(r"(?<!\S)/([a-zA-Z][a-zA-Z0-9_-]*)(?![a-zA-Z0-9_/-])", body)
    for ref in invocations:
        if ref and ref not in known:
            warnings.append(
                f"{path}: references skill '/{ref}' which does not exist in '{skills_dir}'"
            )
    return warnings


def check_thinking_complexity(path: str, frontmatter: dict) -> list[str]:
    """Warn when ``thinking`` capability is combined with ``complexity: small``.

    This combination exhausts iteration budgets prematurely.
    """
    capabilities = frontmatter.get("capabilities") or []
    if isinstance(capabilities, str):
        capabilities = [capabilities]
    if "thinking" in capabilities and frontmatter.get("complexity") == "small":
        return [
            f"{path}: 'thinking' capability combined with 'complexity: small'"
            " — this may exhaust iteration budgets"
        ]
    return []


def check_skill_interface_sections(path: str, body: str) -> list[str]:
    """Warn when a ``.skill.md`` file is missing ``## Input`` or ``## Output`` sections."""
    if not path.endswith(".skill.md"):
        return []
    warnings: list[str] = []
    if not re.search(r"^##\s+Input\b", body, re.MULTILINE):
        warnings.append(f"{path}: .skill.md is missing a '## Input' section")
    if not re.search(r"^##\s+Output\b", body, re.MULTILINE):
        warnings.append(f"{path}: .skill.md is missing a '## Output' section")
    return warnings


def check_stopping_criteria(path: str, body: str) -> list[str]:
    """Warn when no explicit stopping language is found in the agent body.

    This check is opt-in (only active when ``--strict`` is passed to the CLI).
    """
    if not _STOPPING_PHRASES.search(body):
        return [f"{path}: no explicit stopping criteria found in agent body"]
    return []


def check_minimal_body(path: str, body: str) -> list[str]:
    """Warn when the body (non-frontmatter content) is under 100 characters."""
    if len(body) < 100:
        return [f"{path}: body is very short ({len(body)} chars); consider adding more detail"]
    return []
