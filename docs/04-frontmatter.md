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
tools:
  - terminal
  - github
timeout: 300
---
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | string | Yes | — | Display name |
| `description` | string | Yes | — | One-line summary |
| `complexity` | `large` \| `small` | No | `small` | Model tier selection — see below |
| `tools` | list of strings | No | — | Informational only; documents which tool families the agent uses; not enforced by the runtime |
| `timeout` | integer (seconds) | No | 300 | Per-command shell timeout for `run_command` calls |

### Complexity tier resolution

The complexity tier controls which model is selected for a run. The resolution order is (highest priority first):

1. `--complexity` CLI flag
2. `complexity:` field in frontmatter
3. The agent's name appears in `[large_agents].names` in `uio.toml`
4. Default: `small`

Once the tier is resolved, the model is selected based on the provider:

| Provider | `large` | `small` |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | `gemini-2.0-flash-lite` |
| `openai` | `gpt-4o` | `gpt-4o-mini` |
| `ollama` | `qwen2.5-coder:32b` | `qwen2.5-coder:7b` |

Use `complexity: large` for multi-step analysis tasks, code review, or anything where reasoning quality matters more than cost. Use `complexity: small` (the default) for most agents.

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

`uio validate` parses all definition files in the configured directories and checks:

- **Error** (exits non-zero): `name` or `description` is missing or empty
- **Warning** (exits zero): an unrecognised frontmatter key is present

Known keys (do not produce warnings):

```
name  description  complexity  tools  timeout  argument-hint  invokable
```

Any other key produces a warning. This is intentional — it catches typos like `Complexity: large` (capitalised) that would silently be ignored.

---

## Annotated examples

### Full agent

```markdown
---
name: repo-health
description: Run tests, lint, TODO count, stale branches, and open PRs.
complexity: large
tools:
  - terminal
  - github
timeout: 600
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
