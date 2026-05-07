# uio

`uio` is a lightweight, provider-agnostic framework for building the **Agentic Stack** — agents, skills, prompts, and tools — as plain markdown files with YAML frontmatter. The `uio` CLI discovers and executes them against any supported LLM provider. The [origin story](docs/16-about.md) covers how and why.

## Concepts

| Concept | What it is |
|---|---|
| **Agent** | A multi-turn tool-use loop that can execute shell commands and call MCP tools; defined in `*.agent.md` |
| **Skill** | A focused, composable subtask — same loop as an agent, but user-directed via `uio skill run`; defined in `*.skill.md` |
| **Prompt** | A single-shot LLM instruction with no tool loop; defined in `*.prompt.md` |
| **Tool** | An external capability the model invokes mid-loop (MCP tools, `run_command`) — agent-directed, not user-directed |

See the [Glossary](docs/02-concepts.md#glossary) for precise definitions of all terms, including the skill vs tool distinction.

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
    ├── agents/     my-agent.agent.md
    ├── skills/     my-skill.skill.md
    ├── prompts/    my-prompt.prompt.md
    ├── workflows/  my-workflow.workflow.md
    └── memory/
```

See [Writing Definitions](docs/12-writing-definitions.md) for the full file format and authoring guide.

## License

[GNU Affero General Public License v3.0](LICENSE)
