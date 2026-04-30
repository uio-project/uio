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

## Ollama sidecar (no cloud API keys)

Use the bundled `docker-compose.yml` to run `uio` with a local Ollama model — no cloud API keys
required.

```bash
# Pull a model on first run
docker compose run --rm ollama ollama pull qwen2.5-coder:7b

# Run an agent against the local model
docker compose run --rm uio agent run repo-health
```

The compose file wires `OLLAMA_BASE_URL=http://ollama:11434/v1` so `uio` auto-routes to the
local Ollama instance. Cloud keys (`GEMINI_API_KEY`, etc.) are passed through from your host
environment if set, but are not required.

## CI/CD usage

Run `uio` as a step in any container-native pipeline:

```yaml
# GitHub Actions example
- name: Run repo health check
  run: |
    docker run --rm \
      -e GEMINI_API_KEY=${{ secrets.GEMINI_API_KEY }} \
      -e GITHUB_PERSONAL_ACCESS_TOKEN=${{ secrets.GITHUB_TOKEN }} \
      -v ${{ github.workspace }}:/workspace \
      ghcr.io/jomkz/uio agent run repo-health
```

## Building from source

```bash
docker build -t uio .

docker run --rm \
  -e GEMINI_API_KEY=your-key \
  -v $(pwd):/workspace \
  uio skill run summarise "Hello from a local build"
```
