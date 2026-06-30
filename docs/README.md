# uio Documentation

> **New here?** Start with [Installation](01-installation.md), then work through the [Quickstart tutorial](03-quickstart.md).
>
> **Looking for a specific reference?** Jump straight to the [CLI reference](05-cli.md), [Frontmatter schema](04-frontmatter.md), or [Architecture internals](13-internals.md).

---

## Contents

| Page | What it answers |
|---|---|
| [01 — Installation](01-installation.md) | How to install `uio`, set up shell completion, and verify the installation |
| [02 — Core concepts](02-concepts.md) | What agents, skills, and prompts are, and when to use each |
| [03 — Quickstart](03-quickstart.md) | End-to-end tutorial: set a key, scaffold `.uio/`, run your first agent, read the cost report |
| [04 — Frontmatter schema](04-frontmatter.md) | Complete YAML frontmatter reference for `.agent.md`, `.skill.md`, and `.prompt.md` files |
| [05 — CLI reference](05-cli.md) | Every command, subcommand, flag, exit code, and environment variable |
| [06 — Configuration](06-configuration.md) | `uio.toml` key inventory, merge/precedence semantics, and a fully-annotated example |
| [07 — Providers](07-providers.md) | Gemini, OpenAI, Ollama, LiteLLM proxy, and Azure OpenAI — setup, models, and cost table |
| [08 — MCP integration](08-mcp.md) | GitHub MCP server setup, tool naming, custom servers, and the security model |
| [09 — Chat REPL](09-chat.md) | Interactive session options, slash commands, tool approval, and allow/deny glob patterns |
| [10 — Cost ledger](10-cost.md) | Ledger schema, cost formula, `uio cost` usage, and `jq` recipes |
| [11 — Registry](11-registry.md) | Remote registry discovery — configure, search, install, pin, and host a registry |
| [12 — Writing definitions](12-writing-definitions.md) | How to write effective agents, skills, and prompts; tool-use patterns; common failure modes |
| [13 — Internals](13-internals.md) | Package architecture, every module's role, how to add a provider or tool, and contributing |
| [14 — Container image](14-container.md) | Dockerfile, bundled MCP servers, Ollama sidecar, CI/CD usage, and building from source |
| [15 — Use cases](15-use-cases.md) | Worked examples: repo health, code review, issue planning, AI-authored PRs, multi-agent pipelines |
| [16 — About](16-about.md) | The origin story — why uio exists and where the name comes from |
| [17 — GitHub App identities](17-github-app-identities.md) | Dedicated GitHub App identities for agents — setup, frontmatter, and links to governance and runbooks |
| [18 — Design decisions](18-design-decisions.md) | Language choice rationale: why Python, and the CLI startup time trade-off |
| [19 — Memory system](19-memory.md) | `*.memory.md` file format, scope lifecycle, prompt injection, `uio memory` CLI, and `dirs.memory` config key |
| [20 — Positioning](20-positioning.md) | Where uio sits relative to interactive AI tools — comparison table, design rationale, and the CI/CD niche |

---

## Suggested reading paths

### I'm new to uio

1. [Installation](01-installation.md) — get the CLI working
2. [Core concepts](02-concepts.md) — understand the three definition types
3. [Quickstart](03-quickstart.md) — run your first agent
4. [Writing definitions](12-writing-definitions.md) — write your own

### I want to configure a specific provider

- [Providers](07-providers.md) — Gemini, OpenAI, Ollama, LiteLLM, Azure
- [Configuration](06-configuration.md) — persist settings in `uio.toml`

### I want to use the chat REPL

- [Chat REPL](09-chat.md)
- [Providers](07-providers.md) — choose a model

### I want to find and install community definitions

- [Registry](11-registry.md) — `uio registry search` and `uio registry install`

### I want to understand how uio works internally

- [Internals](13-internals.md) — architecture, extension points, contributing
- [Core concepts](02-concepts.md) — mental model first

### I want to run agents with dedicated GitHub App identities

1. [GitHub App identities](17-github-app-identities.md) — overview, frontmatter, and further reading index
2. [Permission matrix](github-permission-matrix.md) — understand what each identity can do
3. [Provisioning guides](provisioning/) — create and install the GitHub Apps
4. [Frontmatter schema](04-frontmatter.md#github-identity) — add `github-identity` to your agent
5. [Configuration](06-configuration.md#github-authentication) — set the required env vars
6. [Governance](governance.md) — ownership, review cadence, and change control
7. [Runbooks](runbooks/) — audit, incident response, credential rotation, emergency disable

### I want to manage issues, labels, and the project board

- [Label & issue-type taxonomy](../.github/labels.md) — types vs. labels, `component:*` routing, meta labels
- [Project setup runbook](runbooks/github-project-setup.md) — milestones (M1–M7), the org Project board, and enabling issue types
- [Contributing — triaging issues](../CONTRIBUTING.md#triaging-issues) — the per-issue triage checklist

### I want to use persistent memory across agent runs

- [Memory system](19-memory.md) — file format, scope lifecycle, prompt injection, and CLI commands
- [Configuration](06-configuration.md#dirs) — override the default `.uio/memory` directory via `dirs.memory`
- [CLI reference — uio memory](05-cli.md#uio-memory) — `list`, `view`, and `clear` commands

### I want to understand how uio compares to interactive tools

- [Positioning](20-positioning.md) — where uio sits, the comparison table, and the CI/CD niche
- [Use cases](15-use-cases.md) — see the positioning in action with end-to-end examples
- [GitHub App identities](17-github-app-identities.md) — one of the key differentiators: per-agent GitHub identities

### I want to see what uio can do end-to-end

- [Use cases](15-use-cases.md) — repo health, code review, issue planning, AI-authored PRs, multi-agent pipelines
