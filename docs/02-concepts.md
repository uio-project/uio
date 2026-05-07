# Core Concepts

## The UIO analogy

The name `uio` comes from Linux's **Userspace I/O** framework. In Linux, UIO lets a kernel device driver export its interface directly to a userspace application — the application calls the device's logic without the kernel needing to know about each specific device type. There is no per-device kernel module, just a generic bridge.

`uio` applies the same idea to AI automation. Your agent and prompt definitions — plain markdown files with YAML frontmatter — export their logic directly to the `uio` CLI. The CLI does not need to know anything about your specific workflow. There is no per-project integration to write; just drop a file into `.uio/` and it becomes a runnable command.

---

## The four definition types

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

### Workflows (`.workflow.md`)

A workflow is a **deterministic pipeline** that chains agents and skills into an ordered sequence of steps. Unlike an agent (which makes its own decisions about what to do next), a workflow's structure is fixed in the definition file — the runtime executes steps one at a time, in order, with no LLM orchestrating the sequence.

Each step specifies which agent or skill to invoke, an optional argument template (with `{{ variable }}` interpolation), an optional output variable to capture the step's final response, and an optional `when:` condition that controls whether the step runs.

**Frontmatter fields:**

- `name` (required) — workflow display name
- `description` (required) — one-line summary
- `steps` (required) — ordered list of step definitions

**Step fields:**

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Step label shown in output |
| `agent` | One of these | Agent stem to invoke (e.g. `reviewer`) |
| `skill` | One of these | Skill stem to invoke (e.g. `summarise`) |
| `arg` | No | Argument string; supports `{{ variable }}` interpolation |
| `output` | No | Variable name to capture the step's final response |
| `when` | No | Skip condition: `<var> contains <substring>` |

**Variable interpolation:**

The run argument is available as `{{ input }}` in every step. Step outputs stored via `output:` are available as `{{ variable_name }}` in subsequent steps.

**`when:` conditions:**

A `when:` condition takes the form `<variable> contains <substring>`. The step is **skipped** when the referenced variable's value does not contain the substring (case-insensitive). If the variable is not yet set, the step is skipped.

**Example workflow:**

```yaml
---
name: review-and-fix
description: Review a PR and open a fix branch if blockers are found.
steps:
  - name: review
    agent: reviewer
    arg: "{{ input }}"
    output: review_result

  - name: fix
    agent: coder
    arg: "{{ input }}"
    when: "review_result contains BLOCKER"
---

# Workflow: review-and-fix

Reviews a pull request using the reviewer agent. If the review output contains
the word "BLOCKER", the coder agent is invoked to open a fix branch.
```

Run with `uio workflow run review-and-fix "owner/repo#42"`.

---

## Comparison table

| | **Agent** | **Skill** | **Prompt** | **Workflow** |
|---|---|---|---|---|
| Tool-use loop | Yes | Yes | No | No (orchestrates others) |
| `run_command` access | Yes | Yes | No | No |
| MCP tool access | Yes | Yes | No | No |
| Iteration cap | 10 | 10 | — | One pass per step |
| Complexity tier | `small` / `large` | `small` / `large` | — | Set per step |
| `steps:` frontmatter | No | No | No | Yes |
| Typical use | Multi-step workflow | Focused subtask | One-shot query | Pipeline of agents/skills |

Tools (`run_command`, MCP tools) are not definition types — they are capabilities the model invokes at runtime. See the [Glossary](#glossary) for the Tool definition and the skill vs tool distinction.

---

## The `.uio/` directory

`.uio/` is your project's AI configuration layer — analogous to `.github/` for GitHub Actions or `.vscode/` for editor settings. It lives at the root of your project and contains your definitions:

```
my-project/
├── .uio/
│   ├── agents/      *.agent.md
│   ├── skills/      *.skill.md
│   ├── prompts/     *.prompt.md
│   ├── workflows/   *.workflow.md
│   └── memory/
├── uio.toml         # optional project config
└── uio_cost.jsonl   # cost ledger (add to .gitignore)
```

Run `uio init` to scaffold this structure. Run `uio init --examples` to also install the bundled example definitions.

The directories are configurable via `uio.toml` (see [Configuration](06-configuration.md)).

---

## How a definition becomes a run

Every `uio agent run` / `uio skill run` / `uio prompt run` / `uio workflow run` invocation:

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
| **Workflows** | `.workflow.md` — deterministic pipelines of agents and skills |
| **Agents** | `.agent.md` — autonomous decision-makers |
| **Skills** | `.skill.md` — composable, user-directed subtasks |
| **Prompts** | `.prompt.md` — single-shot instructions |
| **Tools** | MCP tools + `run_command` — agent-directed capabilities |

This vocabulary is intentional. **"Agentic Stack"** is the umbrella term for the workflows + agents + skills + prompts + tools model that `uio` provides. See the [Glossary](#glossary) below for precise term definitions.

---

## Glossary

| Term | Definition |
|---|---|
| **Agent** | An autonomous decision-maker that runs a multi-turn tool-use loop. Defined in `*.agent.md`. Agents decide when to call tools and how to interpret results. |
| **Skill** | A focused, composable subtask. Runs the same tool-use loop as an agent internally, but is **user-directed**: you invoke it explicitly with `uio skill run <name>`. Skills may also be referenced by name inside agent definition bodies. Skills are small, reusable building blocks; agents are higher-level workflows. |
| **Prompt** | A single-shot LLM instruction. The definition body is sent once and the response is printed — no tool-use loop. Defined in `*.prompt.md`. |
| **Tool** | An external capability the **model** invokes mid-loop. Tools are agent-directed: the agent decides when and how to call them. Examples: `run_command` (built-in), MCP tools such as GitHub or filesystem access. This is the key distinction from skills — a tool is called by the model; a skill is called by you. |
| **Workflow** | A deterministic pipeline that chains agents and skills sequentially. Defined in `*.workflow.md`. The structure is fixed; the runtime executes steps in order with `{{ variable }}` interpolation and optional `when:` conditions — no LLM orchestrates the sequence. |
| **Memory** | Persistent context injected into agent runs across sessions. |
| **Guardrails** | Per-definition constraints on cost, tool access, and iteration count. |
