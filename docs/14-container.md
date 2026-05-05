# Container image

`uio` ships an official container image built on `python:3.11-slim` with Node.js 20 included.
Node.js is required for the GitHub MCP server and the other bundled `@modelcontextprotocol`
packages. The `gh` CLI is also included as a fallback for agents that shell out to GitHub via
`run_command`.

## Bundled MCP servers

The following MCP servers are pre-warmed in the image (no download on first use):

| Server | Package | Tools exposed to the LLM |
|---|---|---|
| GitHub | `@github/github-mcp-server` | `mcp__github__*` — issues, PRs, repos, code search |
| Filesystem | `@modelcontextprotocol/server-filesystem` | `mcp__filesystem__*` — typed file read/write/list |
| Fetch | `@modelcontextprotocol/server-fetch` | `mcp__fetch__*` — typed HTTP GET/POST |
| Memory | `@modelcontextprotocol/server-memory` | `mcp__memory__*` — persistent KV store per session |
| Git | `@modelcontextprotocol/server-git` | `mcp__git__*` — structured git log, diff, blame, show, status, branch, commit. Requires a `path` argument pointing to the repository root. |
| Sequential Thinking | `@modelcontextprotocol/server-sequential-thinking` | `mcp__sequential-thinking__sequentialthinking` — structured reasoning scratchpad; exposes multi-step thought chains as discrete tool calls. |

MCP server configuration is managed via `uio.toml`. See [MCP integration](08-mcp.md) for details.

## Quick start

```bash
# One-shot agent run — mount your project at /workspace
docker run --rm \
  -e GEMINI_API_KEY=your-key \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... \
  -v $(pwd):/workspace \
  ghcr.io/jomkz/uio agent run repo-health

# Interactive skill run
docker run --rm \
  -e GEMINI_API_KEY=your-key \
  -v $(pwd):/workspace \
  ghcr.io/jomkz/uio skill run summarise "Your text here"

# Chat REPL (interactive — allocate a TTY)
docker run --rm -it \
  -e GEMINI_API_KEY=your-key \
  -v $(pwd):/workspace \
  ghcr.io/jomkz/uio chat
```

### Windows users

The examples above use `$(pwd)` (bash/zsh syntax) for the volume mount. In PowerShell use
`${PWD}` instead:

```powershell
docker run --rm `
  -e GEMINI_API_KEY=your-key `
  -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... `
  -v ${PWD}:/workspace `
  ghcr.io/jomkz/uio agent run repo-health
```

If you use `docker compose`, the `.:/workspace` volume path in `docker-compose.yml` is
resolved by Compose and works on all platforms without any change.

## Configuration

`uio.toml` must be present in `/workspace` (the container's working directory). Mount your project
directory at `/workspace` so that `uio.toml` and `.uio/` definitions are picked up automatically.

A minimal `uio.toml` for the container:

```toml
[runtime]
default_provider = "gemini"

[mcp.github]
command = "npx -y @github/github-mcp-server stdio"

[mcp.filesystem]
command = "npx -y @modelcontextprotocol/server-filesystem /workspace"

[mcp.fetch]
command = "npx -y @modelcontextprotocol/server-fetch"

[mcp.memory]
command = "npx -y @modelcontextprotocol/server-memory"

[mcp.git]
command = "npx -y @modelcontextprotocol/server-git /workspace"

# Optional: structured reasoning scratchpad for planning/review agents
# [[mcp.plugins]]
# name    = "sequential-thinking"
# type    = "think"
# command = "npx -y @modelcontextprotocol/server-sequential-thinking"
```

## Stateful paths

| Path | Purpose | Recommendation |
|---|---|---|
| `/workspace/uio.toml` | Project config | Volume-mount your project directory |
| `/workspace/.uio/` | Agent/skill/prompt definitions | Volume-mount your project directory |
| `/workspace/uio_cost.jsonl` | Cost ledger | Volume-mount if persistence is needed |
| `~/.cache/uio/registries/` | Registry manifest cache | Ephemeral — re-fetched on demand |

For one-shot CI runs, none of these need to persist. For long-running or scheduled containers,
mount a named volume at `/workspace`.

## API keys

Pass API keys as environment variables at runtime. Never bake them into the image.

```bash
docker run --rm \
  -e GEMINI_API_KEY=$GEMINI_API_KEY \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=$GITHUB_PERSONAL_ACCESS_TOKEN \
  -v $(pwd):/workspace \
  ghcr.io/jomkz/uio agent run my-agent
```

### GitHub authentication in containers

**Standard agents** (no `github-identity`): pass `GITHUB_PERSONAL_ACCESS_TOKEN` as above.

**Identity agents** (`github-identity: planner | coder | reviewer`): pass the three App
credential variables instead. The private key must be mounted into the container — never
embed the key as an env var value:

```bash
docker run --rm \
  -e GITHUB_APP_CODER_ID=$GITHUB_APP_CODER_ID \
  -e GITHUB_APP_CODER_INSTALLATION_ID=$GITHUB_APP_CODER_INSTALLATION_ID \
  -e GITHUB_APP_CODER_PRIVATE_KEY=/run/secrets/uio-ai-coder.pem \
  -v ~/.config/uio/uio-ai-coder.private-key.pem:/run/secrets/uio-ai-coder.pem:ro \
  -v $(pwd):/workspace \
  ghcr.io/jomkz/uio agent run github-coder "..."
```

Identity agents will **not** fall back to `GITHUB_PERSONAL_ACCESS_TOKEN` — if the App
credentials are absent the runner exits with an actionable error. See
[`docs/06-configuration.md`](06-configuration.md#github-authentication) for details.

## Ollama sidecar (no cloud API keys)

The bundled `docker-compose.yml` runs `uio` alongside a local Ollama instance. No cloud API
keys are required — the entire stack runs with no egress, making it suitable for air-gapped
environments and regulated on-premises deployments.

### How provider routing works with the sidecar

`uio` tries providers in order: **Ollama → OpenAI → Gemini → Anthropic**. A provider is included only if
its API key is present in the environment. Ollama has no key requirement and is always the
first option tried when no cloud keys are set.

The compose file wires `OLLAMA_BASE_URL=http://ollama:11434/v1` so the uio container reaches
the Ollama sidecar over the compose network. With no cloud keys set:

```
ROUTING_CHAIN: [ollama]  ← only Ollama is available, selected immediately
```

With cloud keys set (passed through from the host), cloud providers are added to the chain after Ollama:

```
ROUTING_CHAIN: [ollama, openai, gemini, anthropic]  ← Ollama first; cloud providers tried in order
```

### First-time setup

```bash
# Pull the default model (≈5 GB, good for most agents)
docker compose run --rm ollama ollama pull llama3.1:8b

# Verify — run a skill
docker compose run --rm uio skill run summarise "Hello from Ollama"
```

The `ollama` service persists downloaded models in a named volume (`ollama_data`) so you only
pull once. The uio service waits for the Ollama healthcheck to pass before starting, so there
is no need to manually sequence the startup.

### Model tiers

`uio` selects between a small and a large model based on the agent's complexity setting. With
Ollama, the defaults are:

| Tier | Model | VRAM (approx.) | Use when |
|---|---|---|---|
| `small` (default) | `llama3.1:8b` | ~5 GB | Most agents and skills |
| `large` | `llama3.1:8b` | ~5 GB | Complex multi-step agents, `complexity: large` frontmatter |

Both tiers use the same model by default. Pull it once:

```bash
docker compose run --rm ollama ollama pull llama3.1:8b
```

Force the large tier for a single run:

```bash
docker compose run --rm uio agent run repo-health --complexity large
```

Or set it permanently in the agent's frontmatter:

```yaml
---
name: my-agent
complexity: large
---
```

### Pinning a model

To bypass tier selection entirely and use any Ollama model (including ones not in the default
table), set `LLM_MODEL` before running:

```bash
# Use llama3.2 instead of llama3.1:8b
docker compose run --rm ollama ollama pull llama3.2
LLM_MODEL=llama3.2 docker compose run --rm uio skill run summarise "Hello"
```

`LLM_MODEL` is passed through from the host by the compose file. It overrides tier selection
for all providers — see [Providers](07-providers.md#model-override) for the full resolution
order.

### GPU acceleration (NVIDIA)

The compose file ships a `gpu` profile that replaces the CPU Ollama container with one that
has access to all NVIDIA GPUs on the host.

**Prerequisite:** install [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) on the host.

```bash
# Pull into the GPU container's volume (shared with the CPU container)
docker compose --profile gpu run --rm ollama-gpu ollama pull llama3.1:8b

# Run with GPU acceleration
docker compose --profile gpu run --rm uio-gpu agent run repo-health --complexity large
```

The GPU variant is worthwhile for the 32b model; the 7b model runs acceptably on CPU.

### Air-gapped deployment

With no cloud keys in the environment and the Ollama volume pre-populated, the entire stack
runs without any internet access:

1. On a machine with internet: pull models and export the volume.
2. On the air-gapped host: import the volume and run `docker compose up`.

No requests leave the host — Ollama serves models locally, and MCP servers that make network
calls (e.g. `gh mcp server`) are only started if a GitHub token is present.

### Recommended models

| Model | Pull command | Notes |
|---|---|---|
| `llama3.1:8b` | `ollama pull llama3.1:8b` | Default (both tiers) — reliable tool-calling support, ~5 GB VRAM |
| `llama3.2` | `ollama pull llama3.2` | Fast, low VRAM, good for simple skills |
| `mistral` | `ollama pull mistral` | Good instruction following, widely tested |
| `deepseek-r1:7b` | `ollama pull deepseek-r1:7b` | Strong reasoning; slow output |

For agents that use many tool calls, models with reliable tool-calling support (llama3.1, Mistral)
outperform raw-benchmark leaders. Avoid very small models (≤3b) for agentic use — they
reliably fail to format tool calls correctly. uio probes Ollama for tool-call support before
committing to a run and will skip the provider if the probe fails.

## CI/CD usage

Run `uio` as a step in any container-native pipeline:

```yaml
# GitHub Actions example — standard agent (no github-identity)
- name: Run repo health check
  run: |
    docker run --rm \
      -e GEMINI_API_KEY=${{ secrets.GEMINI_API_KEY }} \
      -e GITHUB_PERSONAL_ACCESS_TOKEN=${{ secrets.GITHUB_TOKEN }} \
      -v ${{ github.workspace }}:/workspace \
      ghcr.io/jomkz/uio agent run repo-health
```

For identity agents in CI, store the App credentials as repository secrets and pass them
via `-e GITHUB_APP_<ROLE>_ID`, `-e GITHUB_APP_<ROLE>_INSTALLATION_ID`, and
`-e GITHUB_APP_<ROLE>_PRIVATE_KEY` (pointing to a mounted secret file). Do not pass
`GITHUB_PERSONAL_ACCESS_TOKEN` — identity agents do not use it.

## Building from source

The official Dockerfile installs `uio-ai` from PyPI, so a published version is required via the `UIO_VERSION` build argument:

```bash
docker build --build-arg UIO_VERSION=0.1.0rc2 -t uio .

docker run --rm \
  -e GEMINI_API_KEY=your-key \
  -v $(pwd):/workspace \
  uio skill run summarise "Hello from a local build"
```

Replace `0.1.0rc2` with the version you want to pin. For local development against unreleased code, install directly with `pip install -e .` and run `uio` from your virtual environment instead of using the container.
