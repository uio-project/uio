"""YAML frontmatter parser for .agent.md, .skill.md, and .prompt.md files."""

from __future__ import annotations

import os
import re
from glob import glob
from pathlib import Path

import yaml

from uio.core.identities import KNOWN_ROLES
from uio.core.vcs import KNOWN_CAPABILITY_TYPES

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)", re.DOTALL)

REQUIRED_FIELDS = ("name", "description")

# Matches "# <Type>: <name>" H1 headings
_H1_RE = re.compile(r"^#\s+(\w+):\s+(.+)$", re.MULTILINE)

# Stopping-criteria phrases expected somewhere in agent bodies
_STOPPING_PHRASES = re.compile(
    r"(stop\b|stopping criteria|do not proceed|halt|report and stop|print.*and stop)",
    re.IGNORECASE,
)

# Marker that causes a child body to *replace* the parent body instead of appending.
_OVERRIDE_MARKER = "# Override"


def parse_frontmatter_raw(path: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) for any YAML-frontmatter file."""
    with open(path) as f:
        raw = f.read()
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw.strip()
    return yaml.safe_load(m.group(1)) or {}, m.group(2).strip()


def parse_definition_file(path: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text) for a definition file."""
    return parse_frontmatter_raw(path)


# ---------------------------------------------------------------------------
# Definition inheritance (extends: frontmatter key)
# ---------------------------------------------------------------------------

# Keys that are *not* inherited from the parent — they are always child-specific.
_NON_INHERITED_KEYS = frozenset({"name", "description", "extends"})


def _find_definition_by_name(name: str, search_dirs: list[str]) -> str | None:
    """Return the path of the first definition file whose stem matches *name*.

    Searches *search_dirs* in order, accepting files with any of the standard
    definition extensions (``*.agent.md``, ``*.skill.md``, ``*.prompt.md``).
    Returns ``None`` when no match is found.
    """
    extensions = ("*.agent.md", "*.skill.md", "*.prompt.md")
    for directory in search_dirs:
        for ext in extensions:
            matches = glob(os.path.join(directory, ext))
            for match in matches:
                name_part = Path(match).name
                stem = None
                for ext_suffix in (".agent.md", ".skill.md", ".prompt.md"):
                    if name_part.endswith(ext_suffix):
                        stem = name_part[: -len(ext_suffix)]
                        break
                if stem is None:
                    stem = name_part.split(".")[0]  # fallback for unknown extension types
                if stem == name:
                    return match
    return None


def _collect_uio_dirs(start_path: str) -> list[str]:
    """Return all sub-directories of the nearest ``.uio/`` tree containing *start_path*.

    Walks upward from the directory containing *start_path* until it finds a
    ``.uio/`` directory, then returns all leaf sub-directories within it (agents,
    skills, prompts) as the search scope for parent resolution.

    Falls back to just the directory containing *start_path* when no ``.uio/``
    ancestor is found.
    """
    start_dir = Path(start_path).resolve().parent
    candidate = start_dir
    for _ in range(20):  # guard against runaway traversal
        uio_dir = candidate / ".uio"
        if uio_dir.is_dir():
            # Collect all immediate sub-directories of .uio/
            dirs = [str(uio_dir)]
            for child in uio_dir.iterdir():
                if child.is_dir():
                    dirs.append(str(child))
            return dirs
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    # No .uio/ ancestor found — fall back to the file's own directory
    return [str(start_dir)]


def resolve_inheritance(
    path: str,
    frontmatter: dict,
    body: str,
    *,
    _visited: tuple[str, ...] = (),
    search_dirs: list[str] | None = None,
) -> tuple[dict, str]:
    """Resolve ``extends:`` inheritance and return the merged (frontmatter, body).

    Merge semantics:
    - Frontmatter: parent values are the baseline; child values override them.
      ``name``, ``description``, and ``extends`` are always taken from the child.
    - Body: child body is **appended after parent body** by default.
      If the child body starts with ``# Override``, the child body **replaces**
      the parent body instead of appending.

    Inheritance is resolved recursively so multi-level chains work correctly.
    Cycles are detected via the *_visited* path tuple and raise ``ValueError``.
    """
    extends = frontmatter.get("extends")
    if not extends:
        return frontmatter, body

    abs_path = str(Path(path).resolve())
    if abs_path in _visited:
        chain = " -> ".join(_visited + (abs_path,))
        raise ValueError(f"Inheritance cycle detected: {chain}")

    visited = _visited + (abs_path,)

    if search_dirs is None:
        search_dirs = _collect_uio_dirs(path)

    parent_path = _find_definition_by_name(str(extends), search_dirs)
    if parent_path is None:
        raise FileNotFoundError(
            f"{path}: extends: '{extends}' — no definition named '{extends}' found"
        )

    parent_fm_raw, parent_body_raw = parse_frontmatter_raw(parent_path)

    # Recursively resolve the parent's own inheritance first
    parent_fm, parent_body = resolve_inheritance(
        parent_path,
        parent_fm_raw,
        parent_body_raw,
        _visited=visited,
        search_dirs=search_dirs,
    )

    # Merge frontmatter: parent values as baseline, child overrides (except non-inherited keys)
    merged_fm: dict = {}
    for k, v in parent_fm.items():
        if k not in _NON_INHERITED_KEYS:
            merged_fm[k] = v
    for k, v in frontmatter.items():
        if k != "extends":
            merged_fm[k] = v

    # Merge body
    if body.startswith(_OVERRIDE_MARKER):
        # Child explicitly replaces parent body; strip the marker line itself
        after_marker = body[len(_OVERRIDE_MARKER) :].lstrip("\n")
        merged_body = after_marker
    else:
        if parent_body and body:
            merged_body = parent_body + "\n\n" + body
        elif parent_body:
            merged_body = parent_body
        else:
            merged_body = body

    return merged_fm, merged_body


def check_inheritance_cycles(paths: list[str]) -> list[str]:
    """Return warning strings for any inheritance cycles found across *paths*.

    Each element of *paths* should be the absolute or relative path to a
    definition file.  Files without an ``extends:`` key are skipped silently.
    """
    warnings: list[str] = []
    for path in paths:
        try:
            fm, body = parse_frontmatter_raw(path)
        except Exception:
            continue
        if not fm.get("extends"):
            continue
        try:
            resolve_inheritance(path, fm, body)
        except ValueError as exc:
            warnings.append(str(exc))
        except FileNotFoundError as exc:
            warnings.append(str(exc))
    return warnings


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
        "context",
        "github-identity",  # deprecated alias for vcs-identity
        "vcs-identity",
        "vcs-provider",
        "schema",
        "extends",
    }
    for key in frontmatter:
        if key not in known:
            errors.append(f"{path}: unrecognised frontmatter key '{key}'")

    # guardrails block validation
    guardrails = frontmatter.get("guardrails")
    if guardrails is not None and not isinstance(guardrails, dict):
        errors.append(f"{path}: 'guardrails' must be a mapping, got {type(guardrails).__name__}")

    # capabilities validation
    capabilities = frontmatter.get("capabilities") or []
    if isinstance(capabilities, str):
        capabilities = [capabilities]
    for cap in capabilities:
        if cap not in KNOWN_CAPABILITY_TYPES:
            errors.append(
                f"{path}: unknown capability '{cap}'"
                f" — must be one of {sorted(KNOWN_CAPABILITY_TYPES)}"
            )

    # vcs-identity validation
    vcs_identity = frontmatter.get("vcs-identity")
    if vcs_identity is not None:
        if vcs_identity not in KNOWN_ROLES:
            errors.append(
                f"{path}: invalid 'vcs-identity' value '{vcs_identity}'"
                f" — must be one of {sorted(KNOWN_ROLES)}"
            )

    # github-identity is the deprecated predecessor of vcs-identity
    identity = frontmatter.get("github-identity")
    if identity is not None:
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
    identity = frontmatter.get("vcs-identity") or frontmatter.get("github-identity")
    if not identity or identity not in KNOWN_ROLES:
        return []

    provider = frontmatter.get("vcs-provider", "github")
    if provider != "github":
        # Non-GitHub providers use different env vars; skip this check for now.
        return []

    from uio.providers.github.app import env_vars_present

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


def _strip_code_spans(text: str) -> str:
    """Remove fenced code blocks and inline code spans from markdown text."""
    # Fenced blocks: backtick and tilde variants (with optional info string)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.DOTALL)
    # Inline spans: match an opening run of N backticks, content, then the same N closing
    # backticks. This correctly handles both `code` and ``code with `backtick` inside``.
    text = re.sub(r"(`+).+?\1", "", text, flags=re.DOTALL)
    return text


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

    # Strip fenced code blocks and inline code spans before scanning so that
    # /word tokens inside documentation examples do not produce false positives.
    scannable = _strip_code_spans(body)

    # Match /skill-name invocations: only standalone tokens preceded by whitespace or
    # start-of-string. The lookahead (?![a-zA-Z0-9_/-]) requires the token to end at a
    # non-word, non-slash boundary, which also prevents regex backtracking from
    # producing spurious short matches inside path segments like /tmp/foo.
    invocations = re.findall(r"(?<!\S)/([a-zA-Z][a-zA-Z0-9_-]*)(?![a-zA-Z0-9_/-])", scannable)
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


# Providers that support structured output via a JSON schema parameter.
_SCHEMA_SUPPORTED_PROVIDERS = frozenset({"openai", "gemini"})


def check_schema_support(path: str, frontmatter: dict, provider: str | None) -> list[str]:
    """Warn when ``schema:`` is declared but the selected provider does not support it.

    Returns an empty list when:
    - ``schema:`` is not set in the frontmatter, or
    - *provider* is ``None`` (provider is resolved at runtime), or
    - the provider is known to support structured output.

    Returns a one-element warning list otherwise.
    """
    if frontmatter.get("schema") is None:
        return []
    if provider is None:
        return []
    if provider in _SCHEMA_SUPPORTED_PROVIDERS:
        return []
    return [
        f"{path}: 'schema:' is declared but provider '{provider}' does not support"
        " structured output — only 'openai' and 'gemini' are supported"
    ]


_WORKFLOW_KNOWN_KEYS = {"name", "description", "steps"}
_STEP_KNOWN_KEYS = {"name", "agent", "skill", "prompt", "arg", "output", "when"}


def validate_workflow_definition(path: str, frontmatter: dict) -> list[str]:
    """Return error strings for a *.workflow.md file."""
    errors = []
    for field in REQUIRED_FIELDS:
        if not frontmatter.get(field):
            errors.append(f"{path}: missing required field '{field}'")
    for key in frontmatter:
        if key not in _WORKFLOW_KNOWN_KEYS:
            errors.append(f"{path}: unrecognised workflow frontmatter key '{key}'")
    steps = frontmatter.get("steps")
    if steps is None:
        errors.append(f"{path}: missing required field 'steps'")
    elif not isinstance(steps, list):
        errors.append(f"{path}: 'steps' must be a list, got {type(steps).__name__}")
    return errors


def check_workflow_steps(path: str, frontmatter: dict) -> list[str]:
    """Warn about individual step problems in a *.workflow.md file."""
    warnings = []
    steps = frontmatter.get("steps") or []
    if not isinstance(steps, list):
        return warnings
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            warnings.append(f"{path}: step {i + 1} is not a mapping")
            continue
        for key in step:
            if key not in _STEP_KNOWN_KEYS:
                warnings.append(f"{path}: step {i + 1} has unrecognised key '{key}'")
        has_agent = "agent" in step
        has_skill = "skill" in step
        has_prompt = "prompt" in step
        type_count = sum([has_agent, has_skill, has_prompt])
        if type_count > 1:
            warnings.append(
                f"{path}: step {i + 1} defines multiple step types ('agent', 'skill', 'prompt' are mutually exclusive)"
            )
        elif type_count == 0:
            warnings.append(f"{path}: step {i + 1} has neither 'agent', 'skill', nor 'prompt'")
    return warnings
