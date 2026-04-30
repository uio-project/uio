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
