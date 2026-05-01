# uio

`uio` is a lightweight, provider-agnostic framework for defining and running AI agents, skills, and prompts. Definitions live as markdown files with YAML frontmatter. The `uio` CLI discovers and executes them against any supported LLM provider. The [origin story](docs/16-about.md) covers how and why.

## Concepts

| Concept | What it is |
|---|---|
| **Agent** | A multi-turn agentic loop that can execute shell commands and call MCP tools |
| **Skill** | A reusable module invoked by agents to perform a focused, composable task |
| **Prompt** | A single-shot LLM instruction for one well-defined workflow |

## Documentation

Full documentation lives in [`docs/`](docs/README.md) — covering installation, core concepts, a quickstart, CLI reference, configuration, providers, MCP integration, the chat REPL, cost ledger, registry, writing definitions, etc.

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

## License

[GNU Affero General Public License v3.0](LICENSE)
