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
    },
    "runtime": {
        "default_provider": None,
        "cost_ledger": "uio_cost.jsonl",
        "timeout": 300,
    },
    "large_agents": {
        "names": [],
    },
}

_STARTER_TOML = """\
[dirs]
agents  = ".uio/agents"
skills  = ".uio/skills"
prompts = ".uio/prompts"

[runtime]
# default_provider = "gemini"
cost_ledger      = "uio_cost.jsonl"
timeout          = 300

[large_agents]
# Agent names that always use the large model tier (in addition to
# any agents that set complexity: large in their frontmatter).
names = []

# [mcp.github]
# command = "npx -y @github/github-mcp-server stdio"
"""


def load_config(path: str = "uio.toml") -> dict:
    """Return merged config dict with built-in defaults."""
    raw: dict = {}
    if tomllib is not None and os.path.exists(path):
        with open(path, "rb") as f:
            raw = tomllib.load(f)

    return {
        "dirs": {**_DEFAULTS["dirs"], **raw.get("dirs", {})},
        "runtime": {**_DEFAULTS["runtime"], **raw.get("runtime", {})},
        "large_agents": {
            "names": raw.get("large_agents", {}).get("names", []),
        },
        "mcp": raw.get("mcp", {}),
    }


def get_starter_toml() -> str:
    return _STARTER_TOML
