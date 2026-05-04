"""Abstract VCS tool name mapping for provider-agnostic agent definitions.

Agents declare ``capabilities: [vcs]`` in their frontmatter and use ``vcs__*``
tool names in their bodies.  At runtime the runner injects a preamble section
that maps each abstract name to the concrete MCP tool name for the active
provider (github, gitlab, …).

Adding a new provider: add an entry to ``VCS_TOOL_MAP`` with the same abstract
keys.  Missing keys are silently omitted from the alias table.
"""

from __future__ import annotations

# Abstract → concrete tool name mapping per VCS provider.
# Keys are the abstract names agents use; values are the actual MCP tool names.
VCS_TOOL_MAP: dict[str, dict[str, str]] = {
    "github": {
        "vcs__list_pull_requests": "mcp__github__list_pull_requests",
        "vcs__create_pull_request": "mcp__github__create_pull_request",
        "vcs__get_pull_request": "mcp__github__get_pull_request",
        "vcs__merge_pull_request": "mcp__github__merge_pull_request",
        "vcs__list_issues": "mcp__github__list_issues",
        "vcs__create_issue": "mcp__github__create_issue",
        "vcs__get_issue": "mcp__github__get_issue",
        "vcs__update_issue": "mcp__github__update_issue",
        "vcs__add_issue_comment": "mcp__github__add_issue_comment",
        "vcs__get_file_contents": "mcp__github__get_file_contents",
        "vcs__create_or_update_file": "mcp__github__create_or_update_file",
        "vcs__push_files": "mcp__github__push_files",
        "vcs__create_branch": "mcp__github__create_branch",
        "vcs__list_branches": "mcp__github__list_branches",
        "vcs__search_code": "mcp__github__search_code",
        "vcs__search_repositories": "mcp__github__search_repositories",
    },
    "gitlab": {
        "vcs__list_pull_requests": "mcp__gitlab__list_merge_requests",
        "vcs__create_pull_request": "mcp__gitlab__create_merge_request",
        "vcs__get_pull_request": "mcp__gitlab__get_merge_request",
        "vcs__list_issues": "mcp__gitlab__list_issues",
        "vcs__create_issue": "mcp__gitlab__create_issue",
        "vcs__get_issue": "mcp__gitlab__get_issue",
        "vcs__update_issue": "mcp__gitlab__update_issue",
        "vcs__add_issue_comment": "mcp__gitlab__create_note",
        "vcs__get_file_contents": "mcp__gitlab__get_file",
        "vcs__create_or_update_file": "mcp__gitlab__create_or_update_file",
        "vcs__push_files": "mcp__gitlab__push_files",
        "vcs__create_branch": "mcp__gitlab__create_branch",
        "vcs__list_branches": "mcp__gitlab__list_branches",
        "vcs__search_code": "mcp__gitlab__search",
    },
}

# Canonical list of recognised capability type strings.
KNOWN_CAPABILITY_TYPES: frozenset[str] = frozenset(
    [
        "vcs",
        "db",
        "browser",
        "search",
        "chat",
        "tracker",
        "ci",
        "cloud",
        "docs",
        "monitor",
        "email",
        "vector",
        "container",
        "fs",
        "http",
        "kv",
        "git",
        "thinking",
    ]
)


def build_tool_alias_section(provider: str) -> str:
    """Return a Markdown preamble block listing the abstract→concrete tool aliases.

    Injected into the system prompt when the agent declares ``capabilities: [vcs]``
    so the LLM knows that ``vcs__*`` names map to real MCP tools.
    """
    mapping = VCS_TOOL_MAP.get(provider)
    if not mapping:
        return ""

    rows = "\n".join(
        f"| `{abstract}` | `{concrete}` |" for abstract, concrete in sorted(mapping.items())
    )
    return f"""\
## VCS Tool Aliases — provider: {provider}

Use the abstract `vcs__*` names below; they map to the concrete MCP tools for
the active provider.  Both forms are accepted, but `vcs__*` names are preferred
so the agent body stays provider-agnostic.

| Abstract name | Concrete MCP tool |
|---|---|
{rows}

---
"""
