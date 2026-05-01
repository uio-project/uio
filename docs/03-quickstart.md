# Quickstart

This tutorial takes you from a fresh install to running your first agent and reading a cost report. It assumes you have already installed uio (see [Installation](01-installation.md)).

Total time: about ten minutes.

---

## Step 1 — Set an API key

uio needs at least one LLM provider. Gemini is the cheapest and easiest to start with:

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and create an API key.
2. Export it in your terminal:

```bash
export GEMINI_API_KEY=your-key-here
```

To make this permanent, add the export line to your `~/.bashrc` (or `~/.zshrc`).

If you prefer OpenAI, use `export OPENAI_API_KEY=your-key-here` instead. For a fully offline option, see [Providers — Ollama](07-providers.md#ollama) — no API key required.

Confirm uio can see the key:

```bash
uio config show
# gemini  GEMINI_API_KEY  ✓ set
```

---

## Step 2 — Scaffold your project

Navigate to any directory (a git repo works well):

```bash
cd ~/my-project
uio init --examples
```

Expected output:

```
  Created directory: .uio/agents/
  Created directory: .uio/skills/
  Created directory: .uio/prompts/
  Created: .uio/agents/example.agent.md
  Created: .uio/skills/example.skill.md
  Created: .uio/prompts/example.prompt.md
  Created: .uio/agents/shell-helper.agent.md
  Created: .uio/agents/repo-health.agent.md
  Created: .uio/skills/summarise.skill.md
  Created: .uio/skills/explain-code.skill.md
  Created: .uio/skills/changelog-entry.skill.md
  Created: .uio/skills/debug-traceback.skill.md
  Created: .uio/prompts/ask-docs.prompt.md
  Added 'uio_cost.jsonl' to .gitignore

Done. Run 'uio agent list' to see available agents.
```

`--examples` installs seven bundled real-world definitions. Without `--examples`, only the three starter template files (example.agent.md, example.skill.md, example.prompt.md) are created.

---

## Step 3 — Explore available definitions

```bash
uio agent list
```

```
  NAME          COMPLEXITY  DESCRIPTION
  example       small       A starter agent — edit to fit your workflow.
  repo-health   large       Run tests, lint, TODO count, stale branches, and open PRs.
  shell-helper  small       Suggest a shell command for a task and optionally run it.
```

```bash
uio skill list
```

```
  NAME             DESCRIPTION
  changelog-entry  Turn a git diff into a conventional-commit changelog entry.
  debug-traceback  Explain a Python traceback and suggest a fix.
  example          A starter skill — edit to fit your workflow.
  explain-code     Explain a source file in plain English.
  summarise        Summarise text or a file.
```

---

## Step 4 — Run a skill

Skills are great for quick, focused tasks. Let's summarise some text:

```bash
uio skill run summarise "Pipes in Unix connect the stdout of one process to the stdin of another, letting you compose small programs into powerful one-liners."
```

The model responds with a concise summary. You'll see the provider and model used printed at the start:

```
  [uio] Running skill 'summarise' via gemini/gemini-2.5-flash-lite

Unix pipes connect process outputs to inputs, enabling powerful composition of small programs.
```

---

## Step 5 — Run an agent with tool use

Agents can execute shell commands. Let's ask `shell-helper` for a command:

```bash
uio agent run shell-helper "show me all git branches sorted by last commit date"
```

When the model wants to run a command, uio prints it and asks for your approval:

```
  [uio] Running agent 'shell-helper' via gemini/gemini-2.5-flash-lite

  $ git branch --sort=-committerdate
  Execute? [Y/n]
```

Press Enter (or `y`) to approve. The command runs and the output is fed back to the model, which then produces its final answer.

To skip approval for all commands, use `--auto-approve`:

```bash
uio agent run shell-helper "show disk usage of the top 5 directories" --auto-approve
```

---

## Step 6 — Inspect a definition

Before editing, look at what's inside:

```bash
uio skill inspect summarise
```

```
  name        : summarise
  description : Summarise text or a file
  ---
  # Skill: Summarise

  You are a precise summariser. When given text or a file path, produce a
  concise summary that captures the key points in plain English. Aim for
  1–3 sentences unless the input is very long.
  ...
```

---

## Step 7 — Edit a definition

Open `.uio/skills/summarise.skill.md` in any editor. Change the instruction in the body — for example, ask for bullet points instead of prose. Save the file and re-run the same skill:

```bash
uio skill run summarise "Unix pipes connect process stdout to stdin."
```

The change takes effect immediately — there is no reload or restart step.

---

## Step 8 — Check your cost

```bash
uio cost
```

```
  TIMESTAMP            AGENT        PROVIDER  MODEL                     TOKENS  COST
  ───────────────────────────────────────────────────────────────────────────────────
  2026-04-30 12:01:05  summarise    gemini    gemini-2.5-flash-lite        892  $0.000089
  2026-04-30 12:02:14  shell-helper gemini    gemini-2.5-flash-lite       1243  $0.000124

Total: 2 run(s) | 2,135 tokens | $0.000213
```

The ledger is stored in `uio_cost.jsonl` (already in your `.gitignore`). See [Cost ledger](10-cost.md) for filtering and `jq` recipes.

---

## What's next

- **Write your first agent**: copy `.uio/agents/example.agent.md` and edit the body to describe your task. See [Writing definitions](12-writing-definitions.md).
- **Configure a different provider**: see [Providers](07-providers.md).
- **Search for community definitions**: see [Registry](11-registry.md).
- **Start an interactive chat session**: `uio chat` — see [Chat REPL](09-chat.md).
- **Understand the full CLI**: see [CLI reference](05-cli.md).
