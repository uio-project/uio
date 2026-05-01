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

Full documentation lives in [`docs/`](docs/README.md) — covering installation, core concepts, a step-by-step quickstart, CLI reference, configuration, providers, MCP integration, the chat REPL, cost ledger, registry, writing definitions, package internals, and [GitHub App identity agents](docs/governance.md).

See [Use Cases](docs/15-use-cases.md) for end-to-end worked examples.

## Quickstart

```bash
pip install uio-ai

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

## GitHub App identities

uio supports dedicated GitHub App identities for agents that act on GitHub — separate
non-human service accounts for planning, coding, and reviewing work:

| Identity | Agent | Operations |
|---|---|---|
| AI Planner | `github-planner` | Create issues · Comment on issues and PRs · Summarize milestones |
| AI Coder | `github-coder` | Create branches · Commit code · Open pull requests |
| AI Reviewer | `github-reviewer` | Read diffs · Post structured review comments |

Declare the identity in your agent's frontmatter:

```yaml
---
name: my-github-agent
github-identity: coder   # planner | coder | reviewer
tools: [terminal, github]
---
```

uio obtains a short-lived GitHub App installation token before the agent loop starts and
sets `GH_TOKEN` — both the `gh` CLI and GitHub MCP server pick it up automatically. All
three agents are available in [uio-registry](https://github.com/jomkz/uio-registry).

See [Governance](docs/governance.md) and [Provisioning guides](docs/provisioning/) for setup.

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
| `gemini` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` |
| `openai` | `gpt-4o` | `gpt-4o-mini` |
| `ollama` | `llama3.1:8b` | `llama3.1:8b` |

## Container image

```bash
# bash/zsh
docker run --rm \
  -e GEMINI_API_KEY=your-key \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... \
  -v $(pwd):/workspace \
  ghcr.io/jomkz/uio agent run repo-health

# PowerShell (Windows) — use ${PWD} instead of $(pwd)
docker run --rm `
  -e GEMINI_API_KEY=your-key `
  -e GITHUB_PERSONAL_ACCESS_TOKEN=ghp_... `
  -v ${PWD}:/workspace `
  ghcr.io/jomkz/uio agent run repo-health

# Cross-platform — docker compose avoids the $(pwd) issue entirely
docker compose run --rm uio agent run repo-health
```

The image includes Node.js and pre-warmed MCP servers (`@github/github-mcp-server`,
`server-filesystem`, `server-fetch`, `server-memory`). A `docker-compose.yml` for local Ollama
use is included in the repo. See [Container image](docs/14-container.md) for full details.

## License

[GNU Affero General Public License v3.0](LICENSE)
