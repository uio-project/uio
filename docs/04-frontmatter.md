# Frontmatter Schema Reference

Every uio definition file starts with a YAML frontmatter block delimited by `---`:

```
---
name: My Agent
description: Does something useful.
complexity: small
---

# Agent body starts here
```

The frontmatter is parsed by `uio/schema/parser.py`. Unknown keys produce a warning from `uio validate`; missing required fields produce an error that causes `uio validate` to exit non-zero.

---

## Common fields (all types)

These two fields are required on every definition regardless of type.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Display name shown in `list` output and in the cost ledger |
| `description` | string | Yes | One-line summary shown in `list` output |

---

## Agent fields (`.agent.md`)

```yaml
---
name: My Agent
description: Does something useful.
complexity: small
capabilities:
  - vcs
  - thinking
timeout: 300
vcs-identity: planner
---
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | Yes | — | Display name |
| `description` | string | Yes | — | One-line summary |
| `complexity` | `large` \| `small` | No | `small` | Model tier selection — see below |
| `capabilities` | list of strings | No | — | Declares which capability families the agent uses. Enforced by `validate_definition()` — unknown values produce an error. Accepted values: `vcs`, `db`, `browser`, `search`, `chat`, `tracker`, `ci`, `cloud`, `docs`, `monitor`, `email`, `vector`, `container`, `fs`, `http`, `kv`, `git`, `thinking`. (`tools` is an accepted legacy alias.) |
| `timeout` | integer (seconds) | No | 300 | Per-command shell timeout for `run_command` calls |
| `vcs-identity` | `planner` \| `coder` \| `reviewer` | No | — | VCS App identity to obtain for this agent's repository operations — see below |
| `vcs-provider` | `github` \| `gitlab` | No | `github` | VCS platform targeted by `vcs-identity`; controls which MCP tool aliases are injected |
| `github-identity` | `planner` \| `coder` \| `reviewer` | No | — | **Deprecated.** Use `vcs-identity` instead. Accepted as an alias for backwards compatibility. |
| `max_tokens` | integer | No | `16000` | Overrides `runtime.anthropic_max_tokens` for this agent; Anthropic provider only |
| `guardrails` | mapping | No | — | Cost, turn, and tool guardrails — see [`guardrails`](#guardrails) below |
| `context` | string or list of strings | No | — | Glob pattern(s) whose matching files are injected as a `## Context` block in the system prompt; de-duplicated and truncated at `runtime.context_max_tokens` (default 8000) tokens |

### Complexity tier resolution

The complexity tier controls which model is selected for a run. The resolution order is (highest priority first):

1. `--complexity` CLI flag
2. `complexity:` field in frontmatter
3. The agent's name appears in `[large_agents].names` in `uio.toml`
4. Default: `small`

Once the tier is resolved, the model is selected based on the provider:

| Provider | `large` | `small` |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` |
| `openai` | `gpt-4o` | `gpt-4o-mini` |
| `ollama` | `llama3.1:8b` | `llama3.1:8b` |

Use `complexity: large` for multi-step analysis tasks, code review, or anything where reasoning quality matters more than cost. Use `complexity: small` (the default) for most agents.

### `vcs-identity`

When set, uio obtains a short-lived VCS App installation token for the named identity before the agent's tool loop starts, and exports it as `GH_TOKEN`. Both the `gh` CLI and the GitHub MCP server read `GH_TOKEN`, so all VCS operations in the run execute as the declared App identity rather than the user's personal account.

| Value | Identity | Permitted operations |
|---|---|---|
| `planner` | AI Planner | Issue create/edit · Issue comments · PR comments |
| `coder` | AI Coder | Branch create · Commit/push · PR create |
| `reviewer` | AI Reviewer | PR review · Inline PR comments · Diff summary |

**Prerequisites:** three environment variables must be set for the chosen identity:

```
GITHUB_APP_PLANNER_ID               — App's numeric ID
GITHUB_APP_PLANNER_INSTALLATION_ID  — Installation ID for the target repo
GITHUB_APP_PLANNER_PRIVATE_KEY      — PEM key (literal or path to .pem file)
```

Replace `PLANNER` with `CODER` or `REVIEWER` for the other identities.

If the env vars are absent at run time, uio exits with an error listing the missing variables — falling back to `GITHUB_PERSONAL_ACCESS_TOKEN` / `GH_TOKEN` is not permitted for identity agents. An invalid identity value (anything other than `planner`, `coder`, `reviewer`) also causes a hard error at startup.

`uio validate` warns (non-fatally) when `vcs-identity` is declared but the corresponding env vars are not set, so you can catch configuration drift in CI.

### `vcs-provider`

Defaults to `github`. Set to `gitlab` when the agent targets a GitLab instance. When set, uio injects a VCS tool alias table into the system prompt so the agent can use provider-neutral `vcs__*` tool names (e.g. `vcs__list_pull_requests`) that resolve to the correct MCP server's tools at runtime.

```yaml
vcs-identity: coder
vcs-provider: gitlab
```

Non-GitHub providers do not validate `vcs-identity` env vars at startup (env var names vary by installation).

### `github-identity` (deprecated)

`github-identity` is a deprecated alias for `vcs-identity`. It is still accepted by the parser for backwards compatibility, but new definitions should use `vcs-identity`.

See `docs/provisioning/` for setup instructions and `docs/github-permission-matrix.md` for the approved permission model.

### `guardrails`

Optional cost, turn, and tool-blocking limits that apply to a single agent definition. All sub-keys are optional; omit the entire block when none are needed.

| Sub-key | Type | Description |
|---|---|---|
| `max_cost_usd` | float | Abort the run if cumulative USD cost exceeds this value. The cost is checked after each tool-call turn using the provider's token pricing. |
| `max_turns` | integer | Cap the number of tool-call turns for this agent. Overrides the global `runtime.max_turns` setting. |
| `deny_tools` | list of strings | Glob patterns matched against tool names. Any tool whose name matches a pattern is blocked; the run continues and the tool call returns an error result instead of executing. |

```yaml
---
name: safe-agent
description: Runs with strict cost and tool limits.
guardrails:
  max_cost_usd: 0.10
  max_turns: 5
  deny_tools:
    - "mcp__*__delete_*"
    - "run_command"
---
```

### `context`

Inject file contents into the system prompt before the agent body. Accepts a single glob string or a list of glob strings. Matching files are read from the current working directory (the project root at run time), de-duplicated, and assembled into a `## Context` block that appears in the system prompt before the agent's body.

Injection is bounded by `runtime.context_max_tokens` (default: 8000 tokens). When the cap is reached the current file is truncated with a `[truncated — N tokens omitted]` marker and no further files are read. Binary files and files that cannot be opened are silently skipped.

```yaml
---
name: context-aware-agent
description: Reads project config before starting.
context:
  - "uio.toml"
  - "docs/*.md"
---
```

A single glob can also be given as a plain string:

```yaml
context: "README.md"
```

### `max_tokens`

Overrides `runtime.anthropic_max_tokens` (default: 16000) for this specific agent definition. Only applies when the Anthropic provider is selected. Use this to raise the limit for agents that produce long outputs or lower it to constrain costs.

```yaml
---
name: long-output-agent
description: Generates a detailed report.
complexity: large
max_tokens: 32000
---
```

See `docs/07-providers.md` for full details on Anthropic token budgets and extended thinking.

---

## Skill fields (`.skill.md`)

```yaml
---
name: My Skill
description: Does one focused thing.
---
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | Yes | — | Display name |
| `description` | string | Yes | — | One-line summary |

Skills do not have a `complexity` field in frontmatter. When run standalone via `uio skill run`, the complexity defaults to `small` (overridable with `--complexity`). Skills are intentionally minimal — their scope should be small enough that the small model tier is appropriate.

---

## Prompt fields (`.prompt.md`)

```yaml
---
name: my-prompt
description: Answers a focused question about a codebase.
argument-hint: "[topic]"
invokable: true
---
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | Yes | — | Display name (also used as the CLI argument to `uio prompt run`) |
| `description` | string | Yes | — | One-line summary |
| `argument-hint` | string or list | No | — | Shown in `uio prompt list`; describes the expected positional argument |
| `invokable` | boolean | No | `false` | When `true`, a positional `ARG` passed to `uio prompt run <name> <arg>` is appended to the prompt body |

### `argument-hint` as a list

When a prompt accepts multiple argument forms, `argument-hint` can be a YAML list:

```yaml
argument-hint:
  - "[file-path]"
  - "[question]"
```

`uio prompt list` displays all variants.

### How `invokable` works

When `invokable: true` and `uio prompt run my-prompt "what is a closure?"` is run, the argument `"what is a closure?"` is appended as a new line at the end of the prompt body before the request is sent. There is no template interpolation — the body and the argument are concatenated literally. Write the body so it reads naturally with or without the appended argument:

```markdown
---
name: ask-docs
description: Ask a focused question about a codebase.
argument-hint: "[question]"
invokable: true
---

You are a precise technical writer. Answer the following question about this
codebase using only information visible in the source code. Be concise.

Question:
```

When run as `uio prompt run ask-docs "what does the cost ledger store?"`, the final line becomes `Question:\nwhat does the cost ledger store?`

---

## Validation

`uio validate` parses all definition files in the configured directories — agents, skills, prompts, and workflows (`*.workflow.md`) — and checks:

- **Error** (exits non-zero): `name` or `description` is missing or empty
- **Warning** (exits zero): an unrecognised frontmatter key is present

Known keys (do not produce warnings):

```
name  description  complexity  capabilities  tools  timeout  argument-hint  invokable
max_tokens  guardrails  context  github-identity  vcs-identity  vcs-provider
```

Any other key produces an error. This is intentional — it catches typos like `Complexity: large` (capitalised) that would silently be ignored.

In addition, `uio validate` emits a **non-fatal warning** (exits zero) when `vcs-identity` (or the deprecated `github-identity`) is declared but the corresponding `GITHUB_APP_<ROLE>_*` env vars are absent. This flags configuration drift without blocking CI pipelines that run without App credentials.

---

## Annotated examples

### Full agent

```markdown
---
name: repo-health
description: Run tests, lint, TODO count, stale branches, and open PRs.
complexity: large
capabilities:
  - vcs
  - fs
timeout: 600
max_tokens: 32000
guardrails:
  max_cost_usd: 0.50
  deny_tools:
    - "mcp__*__delete_*"
---

# Agent: repo-health

Run a comprehensive health check on this Git repository and produce a
structured report. Check each of the following in order:

1. Run the test suite and report pass/fail counts and any failures.
2. Run the linter and report error and warning counts.
3. Count TODO/FIXME comments across all source files.
4. List branches with no commits in the last 30 days.
5. List open pull requests older than 7 days.

Produce a final Markdown report with a section for each item above.
Use `gh` CLI for GitHub operations.
```

### Agent with sequential thinking

```markdown
---
name: deep-review
description: Multi-step code review with externalised reasoning.
complexity: large
capabilities:
  - thinking
---

Before reviewing, use `mcp__sequential-thinking__sequentialthinking` to plan
your approach. Break the review into steps; revise earlier steps if new
information changes your assessment.

Then produce a structured review with: Summary, Issues Found, Suggestions.
```

### Full skill

```markdown
---
name: summarise
description: Summarise text or a file.
---

# Skill: Summarise

You are a precise summariser. When given text or a file path, produce a
concise summary in 1–3 sentences that captures the key points. Preserve
technical accuracy. Do not add information not present in the input.
```

### Full prompt

```markdown
---
name: ask-docs
description: Ask a focused question about a codebase.
argument-hint: "[question]"
invokable: true
---

You are a precise technical writer. Answer the following question about this
codebase using only information visible in the source code. Be concise and
cite the relevant file or function name where possible.

Question:
```
