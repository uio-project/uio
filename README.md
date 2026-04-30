# uio

> Just as Linux UIO lets kernel device drivers export their interfaces directly to userspace — eliminating the need for a full kernel module per device — **uio** lets AI agent definitions (plain markdown files) export their capabilities directly to a CLI, eliminating the need for a custom integration per project.

`uio` is a lightweight, provider-agnostic framework for defining and running AI agents, skills, and prompts. Definitions live as markdown files with YAML frontmatter. The `uio` CLI discovers and executes them against any supported LLM provider.

## Key concepts

| Concept | What it is |
|---|---|
| **Agent** | A multi-turn agentic loop that can execute shell commands and call MCP tools |
| **Skill** | A reusable module invoked by agents to perform a focused, composable task |
| **Prompt** | A single-shot LLM instruction for one well-defined workflow |

## At a glance

```bash
pip install uio

# Run an agent
uio agent run my-agent

# Interactive chat REPL
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

A minimal agent definition:

```markdown
---
name: My Agent
description: Does something useful.
complexity: small
---

# Agent Persona: My Agent

Your task is to …
```

## Providers

Auto-routes across available providers in order: **Gemini → OpenAI → Ollama**. Override with `--provider` or `uio.toml`.

| Provider | Large model | Small model |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | `gemini-2.0-flash-lite` |
| `openai` | `gpt-4o` | `gpt-4o-mini` |
| `ollama` | `qwen2.5-coder:32b` | `qwen2.5-coder:7b` |

> **Implementation in progress.** See [issue #1](https://github.com/jomkz/uio/issues/1) for the full implementation plan.

## License

[GNU Affero General Public License v3.0](LICENSE)
