"""Load and merge uio.toml project configuration."""

from __future__ import annotations

import os

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_DEFAULTS: dict = {
    "dirs": {
        "agents": ".uio/agents",
        "skills": ".uio/skills",
        "prompts": ".uio/prompts",
        "memory": ".uio/memory",
    },
    "runtime": {
        "default_provider": None,
        "routing_chain": None,
        "cost_ledger": "uio_cost.jsonl",
        "timeout": 300,
        "max_iterations": 10,
        "max_iterations_large": 25,
        "anthropic_max_tokens": 16000,
        "context_max_tokens": 8000,
    },
    "large_agents": {
        "names": [],
    },
    "registries": [],
    "mcp_plugins": [],
}

_STARTER_TOML = """\
[dirs]
agents  = ".uio/agents"
skills  = ".uio/skills"
prompts = ".uio/prompts"
memory  = ".uio/memory"

[runtime]
# default_provider = "gemini"
# routing_chain = ["ollama", "openai", "gemini", "anthropic"]
cost_ledger          = "uio_cost.jsonl"
timeout              = 300
max_iterations       = 10   # small agents (summarise, comment, query)
max_iterations_large = 25   # large agents (github-coder, multi-step workflows)
# anthropic_max_tokens = 16000  # Anthropic only; also overridable per-agent via frontmatter
# context_max_tokens   = 8000   # token cap for context: glob injection (default 8000)

[large_agents]
# Agent names that always use the large model tier (in addition to
# any agents that set complexity: large in their frontmatter).
names = []

# [mcp.github]
# command = "npx -y @github/github-mcp-server stdio"

# [mcp.git]
# command = "npx -y @modelcontextprotocol/server-git /workspace"

# MCP plugin registry — external-provider servers loaded alongside bundled ones.
# 'type' declares the capability class (vcs, db, browser, search, chat, tracker, ci, …).
# 'env_keys' lists required environment variables; uio warns and skips if any are absent.
#
# [[mcp.plugins]]
# name    = "sequential-thinking"
# type    = "think"
# command = "npx -y @modelcontextprotocol/server-sequential-thinking"
#
# [[mcp.plugins]]
# name     = "gitlab"
# type     = "vcs"
# command  = "npx -y @gitlab/mcp-server stdio"
# env_keys = ["GITLAB_TOKEN"]
#
# [[mcp.plugins]]
# name     = "linear"
# type     = "tracker"
# command  = "npx -y @linear/mcp-server stdio"
# env_keys = ["LINEAR_API_KEY"]

# Remote registries — each entry is a Git repo with a registry.yaml manifest.
# Run 'uio registry search <query>' to find definitions.
# Run 'uio registry install <name>' to copy a definition into .uio/.
#
# [[registries]]
# name    = "official"
# url     = "https://github.com/jomkz/uio-registry"
# ref     = "main"           # branch, tag, or commit SHA
# enabled = true
# cache_ttl_hours = 24       # how long to keep the cached manifest
"""


def load_config(path: str = "uio.toml") -> dict:
    """Return merged config dict with built-in defaults."""
    raw: dict = {}
    if tomllib is not None and os.path.exists(path):
        with open(path, "rb") as f:
            raw = tomllib.load(f)

    mcp_raw = raw.get("mcp", {})
    # [[mcp.plugins]] entries are a list under the "plugins" key; extract them so they
    # don't get iterated as inline server entries by make_mcp_clients().
    mcp_plugins = [p for p in mcp_raw.get("plugins", []) if isinstance(p, dict)]
    mcp_inline = {k: v for k, v in mcp_raw.items() if k != "plugins"}

    return {
        "dirs": {**_DEFAULTS["dirs"], **raw.get("dirs", {})},
        "runtime": {**_DEFAULTS["runtime"], **raw.get("runtime", {})},
        "large_agents": {
            "names": raw.get("large_agents", {}).get("names", []),
        },
        "mcp": mcp_inline,
        "mcp_plugins": mcp_plugins,
        "registries": raw.get("registries", []),
    }


def get_starter_toml() -> str:
    return _STARTER_TOML
