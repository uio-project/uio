# CLI Reference

## Command tree

```
uio
├── agent
│   ├── run <name> [arg]
│   ├── list
│   ├── inspect <name>
│   └── new <name>
├── skill
│   ├── run <name> [arg]
│   ├── list
│   ├── inspect <name>
│   └── new <name>
├── prompt
│   ├── run <name> [arg]
│   └── list
├── chat
├── cost
├── config
│   ├── show
│   └── init
├── init
├── validate
├── registry
│   ├── list
│   ├── search <query>
│   ├── update
│   └── install <name>
└── completion [bash|zsh|fish]
```

---

## Global flags

| Flag | Description |
|---|---|
| `--version` | Print version and exit |
| `--help` | Print help for any command |

---

## Shared run flags

The following flags apply to `agent run`, `skill run`, and `prompt run`:

| Flag | Type | Default | Description |
|---|---|---|---|
| `--provider` | `gemini\|openai\|ollama` | auto | Force a specific provider; bypasses the routing chain |
| `--model` | string | inferred | Model name override; bypasses tier selection entirely |
| `--complexity` | `large\|small` | inferred | Complexity tier override |
| `--base-url` | URL | env/config | OpenAI-compatible base URL (LiteLLM, Azure, local proxy) |
| `--timeout` | integer | 300 | Per-command shell timeout in seconds |
| `--no-mcp` | flag | off | Disable GitHub MCP server even when token is set |

---

## `uio agent`

### `uio agent run <name> [arg]`

Runs a named agent from `.uio/agents/<name>.agent.md`.

`NAME` is the stem of the filename (without `.agent.md`).
`ARG` is an optional string appended to the initial user message.

```bash
uio agent run my-agent
uio agent run my-agent "focus on the auth module"
uio agent run my-agent --provider openai --complexity large
uio agent run my-agent --no-mcp
```

Exit code: 0 on success, 1 if the definition file is not found or validation fails.

### `uio agent list`

Lists all `.agent.md` files in the configured agents directory.

Output columns: NAME, COMPLEXITY, DESCRIPTION

```bash
uio agent list
```

### `uio agent inspect <name>`

Prints the frontmatter fields and the first 20 lines of the body for a named agent.

```bash
uio agent inspect repo-health
```

### `uio agent new <name>`

Scaffolds a new `.agent.md` file from a template.

```bash
uio agent new data-pipeline
# Creates .uio/agents/data-pipeline.agent.md
```

---

## `uio skill`

### `uio skill run <name> [arg]`

Runs a named skill from `.uio/skills/<name>.skill.md`. Skills use the same tool-use loop as agents.

```bash
uio skill run summarise "Unix pipes connect process stdout to stdin."
uio skill run explain-code src/main.py
```

Accepts the same shared run flags as `agent run`.

### `uio skill list`

Lists all `.skill.md` files in the configured skills directory.

Output columns: NAME, DESCRIPTION

### `uio skill inspect <name>`

Prints frontmatter and body preview for a named skill.

### `uio skill new <name>`

Scaffolds a new `.skill.md` file from a template.

---

## `uio prompt`

### `uio prompt run <name> [arg]`

Runs a named prompt from `.uio/prompts/<name>.prompt.md`. Single-shot — no tool loop.

`ARG` is only used when `invokable: true` is set in the prompt's frontmatter; it is appended to the prompt body before sending.

```bash
uio prompt run ask-docs "what does the cost ledger store?"
```

Accepts `--provider`, `--model`, `--base-url`. Does not accept `--complexity`, `--timeout`, or `--no-mcp` (no tool loop).

### `uio prompt list`

Lists all `.prompt.md` files.

Output columns: NAME, ARGUMENT, DESCRIPTION

---

## `uio chat`

Starts an interactive streaming multi-turn REPL.

```bash
uio chat
uio chat --provider ollama
uio chat --tools
uio chat --tools --allow 'git *' --deny 'git push*'
uio chat --auto-approve
uio chat --system /path/to/system-prompt.txt
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--provider` | string | auto | LLM provider |
| `--model` | string | inferred | Model override |
| `--base-url` | URL | env | OpenAI-compatible endpoint |
| `--system` | path | built-in | File whose contents become the system prompt |
| `--tools` | flag | off | Expose `run_command` to the model |
| `--auto-approve` | flag | off | Skip per-command approval prompts; implies `--tools` |
| `--allow` | glob | — | Auto-approve commands matching this shell glob (repeatable) |
| `--deny` | glob | — | Always reject commands matching this shell glob (repeatable) |

Slash commands inside the REPL: `/help`, `/clear`, `/cost`, `/exit`, `/quit`

See [Chat REPL](09-chat.md) for full details.

---

## `uio cost`

Summarises token spend from the cost ledger.

```bash
uio cost
uio cost --tail 20
uio cost --since 2026-04-01
uio cost --since "2026-04-30T10:00:00"
uio cost --json
uio cost --json | jq '.estimated_cost_usd'
uio cost --ledger /path/to/other.jsonl
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--tail` | integer | — | Show only the last N entries |
| `--since` | ISO 8601 date | — | Show entries on or after this date/datetime |
| `--json` | flag | off | Emit raw JSON lines (one per entry) instead of a table |
| `--ledger` | path | from config | Path to the cost ledger file |

See [Cost ledger](10-cost.md) for `jq` recipes and the full ledger schema.

---

## `uio config`

### `uio config show`

Prints the resolved configuration: provider chain with key status, default provider/model, MCP status, cost ledger path, and timeout.

```bash
uio config show
```

### `uio config init`

Writes a starter `uio.toml` to the current directory. Does not overwrite an existing file.

```bash
uio config init
```

---

## `uio init`

Scaffolds `.uio/agents/`, `.uio/skills/`, and `.uio/prompts/` with one template file each. Also adds the cost ledger filename to `.gitignore` if a `.gitignore` file exists.

```bash
uio init
uio init --examples
```

| Flag | Description |
|---|---|
| `--examples` | Also install the seven bundled real-world example definitions |

Existing files are skipped (not overwritten).

---

## `uio validate`

Parses all definition files in the configured directories and checks required frontmatter fields. Warns on unrecognised keys.

```bash
uio validate
```

Exit code: 0 if all files are valid, 1 if any errors are found. Warnings do not affect the exit code.

---

## `uio registry`

### `uio registry list`

Lists all registries configured in `uio.toml` with their URL, ref, and enabled status.

### `uio registry search <query>`

Searches across all enabled registries. Matches `name`, `description`, and `tags` (case-insensitive).

```bash
uio registry search summarise
uio registry search code --registry official
```

| Flag | Description |
|---|---|
| `--registry` | Restrict search to the named registry |

### `uio registry update`

Force-refreshes all cached registry manifests. Exits 1 if any registry fails.

```bash
uio registry update
uio registry update --registry official
```

### `uio registry install <name>`

Installs a definition from a registry into the appropriate `.uio/` subdirectory. First match across enabled registries wins.

```bash
uio registry install summarise
uio registry install repo-health --registry official
uio registry install repo-health --pin
uio registry install repo-health --force
```

| Flag | Description |
|---|---|
| `--registry` | Use only this registry when resolving NAME |
| `--pin` | Resolve the registry ref to a commit SHA and print the `uio.toml` stanza to paste |
| `--force` | Overwrite an existing local definition |

---

## `uio completion`

Prints a shell completion script.

```bash
eval "$(uio completion bash)"    # bash
eval "$(uio completion zsh)"     # zsh
uio completion fish | source     # fish
```

---

## Environment variables

| Variable | Purpose | Overridden by |
|---|---|---|
| `GEMINI_API_KEY` | Gemini provider authentication | — |
| `OPENAI_API_KEY` | OpenAI / LiteLLM authentication | — |
| `OPENAI_BASE_URL` | Override OpenAI base URL | `--base-url` flag |
| `OLLAMA_BASE_URL` | Ollama base URL (default: `http://localhost:11434/v1`) | `--base-url` flag |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Enables GitHub MCP server; used for registry fetches | — |
| `GITHUB_TOKEN` | Alternative to `GITHUB_PERSONAL_ACCESS_TOKEN` | — |
| `MCP_GITHUB_COMMAND` | Override MCP server launch command | `[mcp.github].command` in uio.toml |
| `LLM_PROVIDER` | Default provider | `--provider` flag, `uio.toml` `default_provider` |
| `LLM_MODEL` | Default model | `--model` flag |

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error (file not found, validation failed, network error, provider failed) |

All errors are written to stderr. Normal output goes to stdout, making it safe to pipe `uio cost --json`, `uio agent list`, etc.
