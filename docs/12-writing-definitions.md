# Writing Definitions

This page covers how to write effective agents, skills, and prompts — from the basics of file structure to advanced patterns for tool use and reliability.

---

## Definition anatomy

Every definition file has two parts separated by the frontmatter delimiters:

```
---
name: My Agent
description: Does something useful.
complexity: small
---

The body text starts here and becomes the system prompt sent to the model.
```

The frontmatter is parsed by uio; the body is passed verbatim to the LLM as its system instruction. See [Frontmatter schema](04-frontmatter.md) for all available fields.

---

## The hidden preamble

uio injects a runtime preamble into the system prompt *before* your definition body. You will not see it in your file, but the model does. Its content depends on whether MCP tools are available:

**Without MCP** (`--no-mcp` or no token set):

```
## ⚠️ Runtime — MCP Tools Unavailable

You are running inside uio. The ONLY tool available is `run_command`.

MCP tools (mcp__github__*, etc.) do NOT exist in this runtime.
Calling them will return "Unknown tool" and waste an iteration — do not attempt them.

For ALL GitHub operations, use `run_command` with the `gh` CLI.
```

**With MCP** (token set, server started):

```
## ℹ️ Runtime — Tools Available

You are running inside uio. Two tool families are available:

**`run_command`** — execute any shell command ...
**`mcp__github__*`** — native GitHub MCP tools ...
Prefer these over `gh` CLI equivalents for GitHub operations.
```

Your definition body follows immediately after this preamble. You do not need to explain `run_command` to the model — the preamble already does. Focus your body on what *you* want the agent to do.

---

## Writing agent and skill bodies

### State the goal first

The model reads the system prompt before anything else. Put the core task in the first sentence:

```markdown
Run a comprehensive health check on this Git repository and produce a structured report.
```

Not:

```markdown
You are a helpful assistant that is very good at many things and can help with various tasks...
```

### Describe the expected output format

Tell the model exactly what to produce:

```markdown
Produce a Markdown report with these sections:
1. Test results (pass/fail count)
2. Lint summary (error count, first 5 errors)
3. Open PRs older than 7 days
```

### Give explicit stopping criteria

Agents run in a loop until the model produces a response with no tool calls. Without a clear stopping condition, the model may keep calling tools unnecessarily.

Good:

```markdown
When you have gathered all the information above, produce the final report and stop.
Do not run any further shell commands after producing the report.
```

Bad (no stopping condition — model may loop):

```markdown
Investigate this repository thoroughly.
```

### Describe the input for skills

Skills are often given an argument via `ARG`. Make it clear what the argument represents:

```markdown
# Skill: Explain Code

You will receive a file path as input. Read the file using `run_command`
with `cat <path>` and explain what it does in plain English.
Target an audience with basic programming knowledge.
```

### Keep scope narrow for skills

A skill that does one thing well is more composable than one that tries to handle every case:

```markdown
# Skill: Summarise

Produce a concise summary in 1–3 sentences. Do not add information
not present in the input. Do not provide opinions or recommendations.
```

---

## Writing prompt bodies

Prompts are single-shot — no tool loop. The body is sent once and the response is printed.

When `invokable: true`, the argument passed on the command line is appended as a new line at the end of the body. **There is no template substitution** — the argument is concatenated literally. Structure the body so it makes sense with the argument appended:

```markdown
---
name: ask-docs
description: Ask a focused question about a codebase.
argument-hint: "[question]"
invokable: true
---

Answer the following question about this codebase using only information visible
in the source code. Cite the relevant file or function name.

Question:
```

Running `uio prompt run ask-docs "what does the cost ledger store?"` sends:

```
Answer the following question...

Question:
what does the cost ledger store?
```

---

## Tool use patterns

### Reading a file

```
Run `cat path/to/file` to read the contents.
```

The model will call `run_command` with `cat path/to/file`. The output is fed back and the model continues.

### Getting git context

Common patterns the model can use via `run_command`:

```bash
git log --oneline -20           # recent commits
git diff HEAD~1                 # last commit diff
git diff --name-only HEAD~1     # changed files
git blame src/file.py           # line attribution
```

### Calling GitHub

Without MCP — use the `gh` CLI:

```bash
gh issue list --state open --limit 10
gh pr view 42
gh api repos/:owner/:repo/commits
```

With MCP — the model uses `mcp__github__*` tools directly (no shell parsing required):

```
Use mcp__github__list_issues to get open issues.
Use mcp__github__get_file_contents to read a specific file.
```

### Iterative refinement

The agent loop is designed for tasks that require multiple steps. Write the body to guide the model through stages:

```markdown
# Agent: Code Review

Review the staged changes in this repository:

1. Run `git diff --cached` to see the staged changes.
2. Identify potential issues: bugs, missing error handling, security concerns.
3. Run `git log --oneline -5` for context on recent changes.
4. Produce a structured review with: Summary, Issues Found, Suggestions.

Stop after producing the review.
```

The model will call tools for steps 1 and 3, then produce the review in step 4 with no further tool calls.

---

## Complexity tier guidance

| Task type | Recommended tier |
|---|---|
| Summarisation, translation, simple formatting | `small` |
| Single-file code explanation | `small` |
| Multi-file analysis | `large` |
| Code review with reasoning | `large` |
| Security audit | `large` |
| Long tool-use chains with dependencies | `large` |

When in doubt, start with `small` and move to `large` if the output quality is insufficient. The cost difference is often 4–10x.

### When to add `thinking` to your agent's capabilities

If the Sequential Thinking MCP server is configured (see [MCP Integration](08-mcp.md#sequential-thinking-mcp-server)), you can explicitly request it in the agent's body to externalise reasoning before acting.

Add an instruction like this to the agent body for agents that:
- Decompose a large feature into sub-tasks (`github-planner`-style work)
- Review code across multiple files where step ordering matters
- Execute long tool-use chains where an early mistake is expensive to undo

```markdown
Before taking any action, use `mcp__sequential-thinking__sequentialthinking`
to plan your approach. Set nextThoughtNeeded to false only when you have a
complete plan, then execute it.
```

Do **not** use sequential thinking for:
- Simple summarisation or translation skills
- Single-file reads or writes
- Agents with `complexity: small` — the overhead of externalised reasoning exceeds the benefit

The tool is available via MCP whenever the server is running. Declaring `thinking` in `capabilities:` is optional but recommended for agents where sequential reasoning is central — it documents intent:

```yaml
---
name: deep-review
complexity: large
capabilities:
  - github
  - thinking
---
```

See [Frontmatter schema](04-frontmatter.md#agent-fields-agentmd) for the full field reference.

---

## The iteration cap

The runner enforces a per-complexity cap on tool-call iterations:

| Tier | Default cap | `uio.toml` key |
|---|---|---|
| `small` | 10 | `runtime.max_iterations` |
| `large` | 25 | `runtime.max_iterations_large` |

If the model keeps calling tools beyond the cap, the loop stops with a warning that names the key to raise:

```
⚠️  Reached iteration cap (10). Stopping.
   The agent did not finish. Increase max_iterations in uio.toml or use --complexity to change the tier.
```

The last model response is still printed. This usually indicates:
- The task is too open-ended — split it into smaller, focused runs
- The stopping criteria in the body are unclear — add an explicit "stop after producing X" instruction
- The agent needs `complexity: large` in its frontmatter to get the higher cap
- The model is stuck in a loop trying something that isn't working — add error handling guidance ("if the command fails, report the error and stop")

---

## Testing a definition

```bash
# Step 1: validate frontmatter
uio validate

# Step 2: run with the small model first
uio agent run my-agent --complexity small

# Step 3: check cost
uio cost --tail 1

# Step 4: iterate — edit the body, re-run
```

---

## Common failure modes

**Model ignores the argument**

Ensure `invokable: true` is set in frontmatter (for prompts). For agents/skills, the argument is appended to the initial user message — make the body reference it: "You will receive input as the initial user message."

**Output is too verbose / too terse**

Specify the output length explicitly: "Produce a 1–3 sentence summary" or "Produce a detailed report with a section for each item."

**Agent keeps running tool calls that return errors**

Add: "If a command fails, report the error message and stop. Do not retry."

**Agent uses MCP tools that don't exist**

If MCP is disabled, the preamble tells the model. If you see "Unknown tool" errors, check that the token is set or add `--no-mcp` to confirm. The preamble is injected automatically — you do not need to document available tools in the body.

**Output truncated mid-response**

The `run_command` tool truncates output at 32,768 bytes. For large outputs, pipe through `head`, `tail`, or `grep` in the command:

```bash
git log --oneline | head -20
find . -name "*.py" | head -50
```

**Cost is higher than expected**

The model is calling too many tools or the context is growing large. Use `--complexity small`, break the task into smaller runs, or add stopping criteria to the body.
