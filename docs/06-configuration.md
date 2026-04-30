# Configuration (`uio.toml`)

`uio.toml` is an optional project-level configuration file. When present in the current working directory, it sets defaults for that project without requiring environment variables or repeated CLI flags.

---

## When to create `uio.toml`

You need `uio.toml` when you want to:

- Persist a preferred provider or model for a specific project (so you don't need `--provider` every time)
- Point `uio` at definition directories other than `.uio/agents/`, `.uio/skills/`, `.uio/prompts/`
- Mark specific agents as always using the `large` model tier without editing their frontmatter
- Configure remote registries for the team
- Change the cost ledger path or default timeout

If you only ever use one project and set everything via environment variables, you may never need this file.

---

## Creating `uio.toml`

```bash
uio config init
```

This writes a commented starter file to the current directory. You can then uncomment and edit the relevant sections.

---

## File location

`uio.toml` must be in the **current working directory** when `uio` is invoked. There is no upward directory search. If you have multiple projects, each has its own `uio.toml` at its root.

---

## Precedence order

For every configurable setting, the resolution order is (highest priority first):

1. **CLI flag** — `--provider`, `--model`, `--complexity`, etc.
2. **Environment variable** — `LLM_PROVIDER`, `LLM_MODEL`, `OPENAI_BASE_URL`, etc.
3. **`uio.toml`** — `default_provider`, `timeout`, etc.
4. **Built-in default** — see table below

---

## Complete key reference

### `[dirs]`

Paths to definition directories. Relative paths are resolved from the current working directory.

| Key | Default | Description |
|---|---|---|
| `agents` | `.uio/agents` | Directory containing `.agent.md` files |
| `skills` | `.uio/skills` | Directory containing `.skill.md` files |
| `prompts` | `.uio/prompts` | Directory containing `.prompt.md` files |

```toml
[dirs]
agents  = ".uio/agents"
skills  = ".uio/skills"
prompts = ".uio/prompts"
```

You can use absolute paths if your definitions live outside the project tree:

```toml
[dirs]
agents = "/home/alice/shared-agents"
```

---

### `[runtime]`

| Key | Default | Description |
|---|---|---|
| `default_provider` | `null` | Provider to use when no `--provider` flag is given and no `LLM_PROVIDER` env var is set. One of `gemini`, `openai`, `ollama`. |
| `cost_ledger` | `uio_cost.jsonl` | Path to the cost ledger file (relative to CWD) |
| `timeout` | `300` | Default per-command shell timeout in seconds for `run_command` calls |

```toml
[runtime]
default_provider = "gemini"
cost_ledger      = "uio_cost.jsonl"
timeout          = 300
```

---

### `[large_agents]`

| Key | Default | Description |
|---|---|---|
| `names` | `[]` | List of agent names that always use the `large` model tier |

This supplements `complexity: large` in frontmatter — useful when you want to force a tier without editing the definition file:

```toml
[large_agents]
names = ["repo-health", "code-review"]
```

Agent names are matched case-insensitively with hyphens and underscores treated as equivalent (`repo-health` matches `repo_health`).

---

### `[mcp.github]`

| Key | Default | Description |
|---|---|---|
| `command` | `npx -y @github/github-mcp-server stdio` | Full shell command to launch the GitHub MCP server |

Override when `npx` is not available or you want a pinned version:

```toml
[mcp.github]
command = "bun x @github/github-mcp-server@1.2.0 stdio"
```

This section only affects the MCP server launch command. The server still requires
`GITHUB_PERSONAL_ACCESS_TOKEN` or `GITHUB_TOKEN` to be set for agents that do **not**
declare `github-identity`. See [GitHub authentication](#github-authentication) below.

---

### `[[registries]]`

An array of registry configurations. Each entry is a Git repository with a `registry.yaml` manifest.

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | string | required | Identifier used in `uio registry list` and `--registry` filter |
| `url` | string | required | Git repository URL (GitHub, GitLab, or any HTTPS URL) |
| `ref` | string | `main` | Branch name, tag, or commit SHA to fetch from |
| `enabled` | boolean | `true` | When `false`, this registry is skipped by all registry commands |
| `cache_ttl_hours` | integer | — | How long the cached manifest is considered fresh before re-fetching. Omit to always use the cache if it exists |

```toml
[[registries]]
name    = "official"
url     = "https://github.com/jomkz/uio-registry"
ref     = "main"
enabled = true
cache_ttl_hours = 24

[[registries]]
name    = "my-team"
url     = "https://github.com/acme/uio-agents"
ref     = "v1.2.0"
enabled = true
```

See [Registry](11-registry.md) for full registry documentation.

---

## GitHub authentication

uio supports two authentication tracks for GitHub tools:

### Personal Access Token (default)

Set `GITHUB_PERSONAL_ACCESS_TOKEN` (or `GH_TOKEN`) in your environment. The `gh` CLI
and the GitHub MCP server both pick this up automatically. This is the standard path
for agents that do **not** declare `github-identity`.

### GitHub App identity (identity agents)

Agents that declare `github-identity: planner | coder | reviewer` in their frontmatter
**must** authenticate via the corresponding GitHub App installation token. The uio
runner exchanges App credentials for a short-lived token and sets `GH_TOKEN`
automatically before the agent loop begins.

This is not optional — if an agent declares `github-identity` but the App credentials
are not present, the runner hard-fails with an actionable error. Falling back to
`GITHUB_PERSONAL_ACCESS_TOKEN` is explicitly blocked for identity agents.

Required environment variables per identity (store in `~/.config/uio/secrets`):

| Identity | Variables |
|---|---|
| `planner` | `GITHUB_APP_PLANNER_ID`, `GITHUB_APP_PLANNER_INSTALLATION_ID`, `GITHUB_APP_PLANNER_PRIVATE_KEY` |
| `coder` | `GITHUB_APP_CODER_ID`, `GITHUB_APP_CODER_INSTALLATION_ID`, `GITHUB_APP_CODER_PRIVATE_KEY` |
| `reviewer` | `GITHUB_APP_REVIEWER_ID`, `GITHUB_APP_REVIEWER_INSTALLATION_ID`, `GITHUB_APP_REVIEWER_PRIVATE_KEY` |

See [`docs/04-frontmatter.md`](04-frontmatter.md) for the `github-identity` field reference
and [`docs/provisioning/`](provisioning/) for App setup guides.

---

## Fully-annotated example `uio.toml`

```toml
# uio.toml — project-level configuration for uio
# Run 'uio config init' to scaffold this file.

[dirs]
# Where uio looks for definition files.
# Relative to the directory where you run uio.
agents  = ".uio/agents"
skills  = ".uio/skills"
prompts = ".uio/prompts"

[runtime]
# Default provider when no --provider flag or LLM_PROVIDER env var is set.
# Uncomment to pin a provider for this project.
# default_provider = "gemini"

# Path to the cost ledger (append-only JSONL file).
# Add this to .gitignore — uio init does this automatically.
cost_ledger = "uio_cost.jsonl"

# Per-command shell timeout in seconds for run_command tool calls.
# Individual agents can override this with the 'timeout' frontmatter field.
timeout = 300

[large_agents]
# Agent names that always use the large model tier, in addition to
# any agents that set 'complexity: large' in their frontmatter.
# Names are matched case-insensitively; hyphens and underscores are equivalent.
names = []

# Uncomment to override the GitHub MCP server launch command.
# [mcp.github]
# command = "npx -y @github/github-mcp-server stdio"

# Remote registries — Git repos with a registry.yaml manifest at root.
# Run 'uio registry search <query>' to find definitions.
# Run 'uio registry install <name>' to copy a definition into .uio/.
#
# [[registries]]
# name            = "official"
# url             = "https://github.com/jomkz/uio-registry"
# ref             = "main"       # branch, tag, or commit SHA
# enabled         = true
# cache_ttl_hours = 24           # re-fetch manifest after 24 hours
```
