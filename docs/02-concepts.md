# Core Concepts

## The UIO analogy

The name `uio` comes from Linux's **Userspace I/O** framework. In Linux, UIO lets a kernel device driver export its interface directly to a userspace application — the application calls the device's logic without the kernel needing to know about each specific device type. There is no per-device kernel module, just a generic bridge.

`uio` applies the same idea to AI automation. Your agent and prompt definitions — plain markdown files with YAML frontmatter — export their logic directly to the `uio` CLI. The CLI does not need to know anything about your specific workflow. There is no per-project integration to write; just drop a file into `.uio/` and it becomes a runnable command.

---

## The three definition types

Every `uio` definition is a markdown file. The file type is encoded in the filename extension, and the YAML frontmatter at the top controls how the runtime handles it.

### Agents (`.agent.md`)

An agent runs in a **multi-turn tool-use loop**. The definition body becomes the system prompt. The runtime sends the system prompt and an initial user message to the model, then alternates between letting the model call tools and feeding tool results back until the model produces a response with no tool calls (or the 10-iteration cap is reached).

The only built-in tool is `run_command`, which runs any shell command and returns stdout + stderr. If a GitHub token is set, MCP tools are also available (see [MCP integration](08-mcp.md)).

Use an agent when the task requires **intermediate decisions** — reading a file to decide what to do next, running a test to see if a fix worked, querying an API before generating a report.

Example: `repo-health.agent.md` runs tests, counts TODOs, checks for stale branches, and compiles a health report — all in one agentic loop.

### Skills (`.skill.md`)

A skill runs the **same tool-use loop as an agent** but is scoped to a single, focused task intended to be composable. There is no runtime difference between an agent and a skill — the distinction is a convention that communicates intent: skills are small, reusable building blocks; agents are higher-level workflows.

Use a skill when you want something that does one thing well and can be referenced by name in another definition's body.

Example: `summarise.skill.md` takes text (passed as an argument or via stdin) and returns a concise summary.

### Prompts (`.prompt.md`)

A prompt is **single-shot**: the definition body is sent to the model once, the response is printed, and the process exits. There is no tool-use loop.

When `invokable: true` is set in frontmatter, the `uio prompt run <name> <arg>` command appends `arg` to the prompt body before sending. The body should read naturally with the appended argument.

Use a prompt for well-defined, one-shot queries where you want the model to respond directly without needing to run shell commands.

Example: `ask-docs.prompt.md` answers a focused question about a codebase by appending the question as a final line.

---

## Comparison table

| | **Agent** | **Skill** | **Prompt** |
|---|---|---|---|
| Tool-use loop | Yes | Yes | No |
| `run_command` access | Yes | Yes | No |
| MCP tool access | Yes | Yes | No |
| Iteration cap | 10 | 10 | — |
| Complexity tier | `small` / `large` | `small` / `large` | — |
| `invokable` frontmatter | No | No | Optional |
| Typical use | Multi-step workflow | Focused subtask | One-shot query |

---

## The `.uio/` directory

`.uio/` is your project's AI configuration layer — analogous to `.github/` for GitHub Actions or `.vscode/` for editor settings. It lives at the root of your project and contains your definitions:

```
my-project/
├── .uio/
│   ├── agents/    *.agent.md
│   ├── skills/    *.skill.md
│   └── prompts/   *.prompt.md
├── uio.toml       # optional project config
└── uio_cost.jsonl # cost ledger (add to .gitignore)
```

Run `uio init` to scaffold this structure. Run `uio init --examples` to also install the bundled example definitions.

The directories are configurable via `uio.toml` (see [Configuration](06-configuration.md)).

---

## How a definition becomes a run

Every `uio agent run` / `uio skill run` / `uio prompt run` invocation:

1. Reads the definition file fresh from disk (no caching — edits take effect immediately)
2. Parses the YAML frontmatter block
3. Validates required fields (`name`, `description`)
4. Constructs the system prompt (runtime preamble + definition body)
5. Selects a provider and model via the routing chain
6. Optionally starts the GitHub MCP server
7. Runs the tool-use loop (agents/skills) or single-shot request (prompts)
8. Appends a cost entry to `uio_cost.jsonl`

The definition file is the single source of truth for behaviour. Moving, editing, or deleting it immediately affects the next run.

---

## The Agentic Stack

`uio` implements the **Agentic Stack** pattern — a layered model for composable AI automation:

| Layer | uio primitive |
|---|---|
| **Agents** | `.agent.md` — autonomous decision-makers |
| **Skills** | `.skill.md` — composable, user-directed subtasks |
| **Prompts** | `.prompt.md` — single-shot instructions |
| **Tools** | MCP tools + `run_command` — agent-directed capabilities |

This vocabulary is intentional. "Agentic Stack" is the umbrella term for the agents + skills + prompts + tools model that `uio` provides.

---

## Glossary

| Term | Definition |
|---|---|
| **Agent** | An autonomous decision-maker that runs a multi-turn tool-use loop. Defined in `*.agent.md`. Agents decide when to call tools and how to interpret results. |
| **Skill** | A focused, composable subtask. Runs the same tool-use loop as an agent internally, but is **user-directed**: you invoke it explicitly with `uio skill run <name>`. Skills are small, reusable building blocks; agents are higher-level workflows that may reference skills by name. |
| **Prompt** | A single-shot LLM instruction. The definition body is sent once and the response is printed — no tool-use loop. Defined in `*.prompt.md`. |
| **Tool** | An external capability the **model** invokes mid-loop. Tools are agent-directed: the agent decides when and how to call them. Examples: `run_command` (built-in), MCP tools such as GitHub or filesystem access. This is the key distinction from skills — a tool is called by the model; a skill is called by you. |
| **Memory** | Persistent context injected into agent runs across sessions. Not yet implemented; tracked in [#161](https://github.com/jomkz/uio/issues/161). |
| **Guardrails** | Per-definition constraints on cost, tool access, and iteration count. Not yet implemented; tracked in [#160](https://github.com/jomkz/uio/issues/160). |
