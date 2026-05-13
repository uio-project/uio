# uio

`uio` is the agent runtime for CI/CD. Define agents, skills, and prompts as plain markdown files with YAML frontmatter — checked into your repo, executed headlessly in pipelines, and wired to any LLM provider. The [origin story](docs/16-about.md) covers how and why.

## Why uio?

uio occupies a distinct niche: **definition-as-code automation**. The agents, skills,
and prompts you author live in your repo, run headlessly in CI/CD, carry distinct
GitHub App identities, and produce auditable cost records.

Interactive assistants (chat UIs, IDE plugins, terminal REPLs) are what you open when
you want to build something at a terminal. uio is what runs at 3am when no one is
watching.

| Need | Interactive assistant (e.g. Copilot, Cursor) | uio |
|---|---|---|
| Designed for headless CI/CD execution | No | Yes |
| Definitions stored in git | No | Yes — plain markdown files |
| Reproducible across environments | No | Yes — provider-agnostic |
| Scriptable / composable | Limited | Yes — `uio agent run`, `uio skill run` |
| Auditable cost records | No | Yes — JSONL ledger, `uio cost` |
| Multi-agent GitHub identities | No | Yes — planner / coder / reviewer App identities |
| Definition sharing | No | Yes — git-hosted registries |
| Auditable history of changes | No | Yes — git blame, PR diffs |

If your use case is "trigger an agent on push, review its output in a PR" — that is
exactly what uio is designed for. See [docs/20-positioning.md](docs/20-positioning.md)
for the full comparison and rationale.

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
