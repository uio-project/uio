# Memory System

uio supports persistent memory files that inject context into agent and skill runs.
Memory files live in `.uio/memory/` and are loaded automatically at agent startup —
no frontmatter changes needed in your agent definitions.

---

## Overview

Memory lets you pre-load facts, preferences, or session context into every agent run
without embedding them in the agent definition itself. This keeps definitions generic
while allowing project-specific or session-specific context to be injected at runtime.

Memory files are plain Markdown files with a `.memory.md` extension and YAML frontmatter.
Their body content appears in the agent's system prompt under a `## Persistent Memory`
block, each entry in its own named subsection.

---

## File format

Memory files use the same frontmatter-plus-body structure as other uio definitions.

**File naming:** `<anything>.memory.md` — the prefix is arbitrary; files are loaded
alphabetically from the memory directory.

**Complete frontmatter example:**

```markdown
---
name: project-context
description: High-level context about this project injected into every agent run.
scope: project
---

This repository is **my-app** — a Python web service backed by PostgreSQL.

Key facts:
- Main entry point is `src/app.py`
- Tests live in `tests/` and run with `pytest`
- Migrations are managed with Alembic
```

### Frontmatter fields

| Field | Required | Description |
|---|---|---|
| `name` | No / optional (falls back to file stem) | Display name used in the `## Persistent Memory` heading and in `uio memory view <name>` |
| `description` | No | One-line summary (shown in `uio memory list`) |
| `scope` | No | Lifecycle scope: `project` (default) or `session` — see [Scope lifecycle](#scope-lifecycle) below |

The `name` field is used as the subsection heading when the memory block is built.
If `name` is absent, uio falls back to the file stem (e.g. `project-context` for
`project-context.memory.md`).

---

## How memory is injected

At agent startup, uio reads all `*.memory.md` files from the configured memory
directory, filters out empty bodies, and appends a `## Persistent Memory` block at
the end of the system prompt:

```
## Persistent Memory

### project-context

This repository is **my-app** — a Python web service backed by PostgreSQL.
...

---

### session-goals

Current sprint: implement the password-reset flow.
...
```

Each named entry is separated by a horizontal rule (`---`). Files are loaded in
alphabetical order by filename, so you can control injection order by prefixing
filenames (e.g. `01-context.memory.md`, `02-goals.memory.md`).

Memory files with an empty body are silently skipped — they do not produce a heading
or a separator.

---

## Scope lifecycle

The `scope` field controls when a memory file's body is cleared:

### `scope: project` (default)

Project-scoped memory **persists across agent runs**. The body is never automatically
cleared. Use this for stable facts that remain true for the life of the project —
architecture notes, team conventions, key file locations, etc.

```yaml
scope: project
```

### `scope: session`

Session-scoped memory is **cleared at the end of each clean agent run**. The body is
truncated to empty (the frontmatter is preserved) after the agent's tool-use loop
completes successfully. Use this for context that is only meaningful within a single
work session — current goals, in-progress task state, or scratchpad notes.

```yaml
scope: session
```

> **What counts as a clean exit?** Session memory is cleared when the agent
> finishes its tool-use loop without an unhandled exception. This includes both
> a natural finish (the model stops calling tools) and hitting the iteration cap.
> If the agent crashes mid-run (provider error, `KeyboardInterrupt`, etc.)
> the `finally:` block still runs but `_clean_exit` remains `False`, so session
> memory is preserved for the next retry.

---

## Writing to memory files

uio does not write to memory files automatically. Agents can update memory by
emitting a `run_command` tool call that writes to the file directly, for example:

    Append a fact to session memory:
    run_command: echo "- Completed: auth flow refactor" >> .uio/memory/session-goals.memory.md

Alternatively, use `uio memory clear --session` from the command line to reset
session context before the next run.

---

## Directory structure

By default, memory files live in `.uio/memory/`:

```
.uio/
└── memory/
    ├── project-context.memory.md   # scope: project
    └── session-goals.memory.md     # scope: session
```

`uio init` creates the `.uio/memory/` directory automatically when scaffolding a
new project.

---

## Configuration

The memory directory path is controlled by the `dirs.memory` key in `uio.toml`:

| Key | Default | Description |
|---|---|---|
| `dirs.memory` | `.uio/memory` | Directory scanned for `*.memory.md` files |

```toml
[dirs]
memory = ".uio/memory"
```

You can use an absolute path to share memory files across projects:

```toml
[dirs]
memory = "/home/alice/shared-memory"
```

See [Configuration](06-configuration.md) for the full `uio.toml` key reference.

---

## CLI commands

Use `uio memory` to inspect and manage memory files from the command line.

### `uio memory list`

Lists all memory files with name, scope, and estimated body size in tokens:

```
uio memory list
```

```
NAME             SCOPE    TOKENS
---------------  -------  ------
project-context  project  42
session-goals    session  18
```

### `uio memory view <name>`

Prints the full body of the named memory file to stdout:

```
uio memory view project-context
```

`NAME` is matched against the `name` frontmatter field, falling back to the file stem.
Exit code 1 if the named file is not found.

### `uio memory clear [--session]`

Truncates memory file bodies (frontmatter is always preserved):

```
uio memory clear            # truncate ALL memory files (project + session)
uio memory clear --session  # truncate only session-scoped files
```

The `--session` flag is useful when you want to reset session context manually
without discarding project-scoped facts.

For the full CLI reference including flags and exit codes, see
[CLI reference — uio memory](05-cli.md#uio-memory).

---

## Example: project context file

A minimal project context file to get started:

```markdown
---
name: project-context
description: Permanent project facts injected into every agent run.
scope: project
---

Project: <your-project-name>

Key facts:
- Language: <language>
- Test command: <test command>
- Main entry point: <entry point>
```

Save it to `.uio/memory/project-context.memory.md` and every subsequent `uio agent run`
or `uio skill run` will include this block in the system prompt.
