# uio

> Just as Linux UIO lets kernel device drivers export their interfaces directly to userspace — eliminating the need for a full kernel module per device — **uio** lets AI agent definitions (plain markdown files) export their capabilities directly to a CLI, eliminating the need for a custom integration per project.

`uio` is a lightweight, provider-agnostic framework for defining and running AI agents, skills, and prompts. Definitions live as markdown files with YAML frontmatter. The `uio` CLI discovers and executes them against any supported LLM provider.

## Key concepts

| Concept | What it is |
|---|---|
| **Agent** | A multi-turn agentic loop that can execute shell commands and call MCP tools |
| **Skill** | A reusable module invoked by agents to perform a focused, composable task |
| **Prompt** | A single-shot LLM instruction for one well-defined workflow |

## Documentation

Full documentation lives in [`docs/`](docs/README.md) — covering installation, core concepts, a step-by-step quickstart, CLI reference, configuration, providers, MCP integration, the chat REPL, cost ledger, registry, writing definitions, and package internals.

## Quickstart

```bash
pip install uio

# Scaffold .uio/ and install bundled examples
uio init --examples

# Run one of the bundled examples
uio skill run summarise "Your text here"
uio agent run repo-health

# Interactive streaming chat
uio chat

# View token spend
uio cost
```

Definitions live in `.uio/`:

```
my-project/
└── .uio/
    ├── agents/   my-agent.agent.md
    ├── skills/   my-skill.skill.md
    └── prompts/  my-prompt.prompt.md
```

See [Writing Definitions](docs/12-writing-definitions.md) for the full file format and authoring guide.

## Registry

Discover and install community definitions from remote registries — Git repos with a `registry.yaml` manifest. No central server required.

```bash
# Add a registry to uio.toml:
# [[registries]]
# name = "official"
# url  = "https://github.com/jomkz/uio-registry"
# ref  = "main"

uio registry list                   # show configured registries
uio registry search summarise       # search by name, description, or tag
uio registry install summarise      # copy definition into .uio/
uio registry install repo-health --pin  # install and print a pinnable SHA
uio registry update                 # refresh cached manifests
```

Installed definitions are plain local files — no live runtime dependency on the registry.

## Providers

Auto-routes across available providers in order: **Gemini → OpenAI → Ollama**. Override with `--provider` or `uio.toml`.

| Provider | Large model | Small model |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | `gemini-2.0-flash-lite` |
| `openai` | `gpt-4o` | `gpt-4o-mini` |
| `ollama` | `qwen2.5-coder:32b` | `qwen2.5-coder:7b` |

## Container image

```bash
docker run --rm \
  -e GEMINI_API_KEY=your-key \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... \
  -v $(pwd):/workspace \
  ghcr.io/jomkz/uio agent run repo-health
```

The image includes Node.js and pre-warmed MCP servers (`@github/github-mcp-server`,
`server-filesystem`, `server-fetch`, `server-memory`). A `docker-compose.yml` for local Ollama
use is included in the repo. See [Container image](docs/14-container.md) for full details.

## License

[GNU Affero General Public License v3.0](LICENSE)
