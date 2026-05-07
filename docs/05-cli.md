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
├── workflow
│   ├── run <name> [arg]
│   └── list
├── chat
├── cost
├── config
│   ├── show
│   └── init
├── init
├── link
├── mcp
│   └── init
├── memory
│   ├── list
│   ├── view <name>
│   └── clear [--session]
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
| `--provider` | `gemini\|openai\|ollama\|anthropic` | auto | Force a specific provider; bypasses the routing chain |
| `--model` | string | inferred | Model name override; bypasses tier selection entirely |
| `--complexity` | `large\|small` | inferred | Complexity tier override |
| `--base-url` | URL | env/config | OpenAI-compatible base URL (LiteLLM, Azure, local proxy) |
| `--timeout` | integer | 300 | Per-command shell timeout in seconds |
| `--no-mcp` | flag | off | Disable GitHub MCP server even when token is set |
| `--shell` | `bash\|sh\|zsh\|powershell\|pwsh` | auto | Shell for `run_command`; auto-detects platform (PowerShell on Windows, bash/sh on POSIX) |

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
uio agent run my-agent --shell pwsh    # force PowerShell on any platform
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

## `uio workflow`

### `uio workflow run <name> [arg]`

Runs a named workflow sequentially from `.uio/workflows/<name>.workflow.md`. Each step is executed in order; the output of one step is not automatically piped into the next unless the step definition references `{{ input }}`.

`WORKFLOW` is the stem of the filename (without `.workflow.md`).
`ARG` is an optional positional argument injected as `{{ input }}` in step arguments.

```bash
uio workflow run review-and-fix
uio workflow run review-and-fix "owner/repo#42"
uio workflow run review-and-fix --provider openai
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--provider` | `gemini\|openai\|ollama` | auto | LLM provider override for every step; bypasses the routing chain |
| `--model` | string | inferred | Model name override for every step |
| `--no-mcp` | flag | off | Disable all MCP servers for every step |
| `--shell` | `bash\|sh\|zsh\|powershell\|pwsh` | auto | Shell for `run_command`; auto-detects platform |

Exit code: 0 on success, 1 if the workflow definition is not found or a step fails.

### `uio workflow list`

Lists all available workflows from the configured workflows directory (`.uio/workflows/*.workflow.md`).

Output columns: NAME, STEPS, DESCRIPTION

```bash
uio workflow list
```

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

Scaffolds `.uio/agents/`, `.uio/skills/`, `.uio/prompts/`, `.uio/workflows/`, and `.uio/memory/` with one template file each in `agents/`, `skills/`, and `prompts/`. Also adds the cost ledger filename to `.gitignore` if a `.gitignore` file exists.

```bash
uio init
uio init --examples
```

| Flag | Description |
|---|---|
| `--examples` | Also install the seven bundled real-world example definitions |

Existing files are skipped (not overwritten).

---

## `uio link`

Creates and maintains platform integration symlinks so that IDE and CI platforms can discover uio definitions.

Reads source directories from `uio.toml` (`dirs.agents`, `dirs.skills`, `dirs.prompts`) and creates the correct symlinks for each platform.

For `.claude/commands/` the command creates **per-file symlinks** that strip the `.prompt` infix so Claude Code discovers them as `/name` rather than `/name.prompt`.

```bash
uio link
uio link --dry-run
uio link --platforms claude
uio link --force
```

| Flag | Description |
|---|---|
| `--platforms` | Comma-separated list of platforms to link: `github,claude`. Default: all. |
| `--dry-run` | Print planned changes without modifying the filesystem. |
| `--force` | Replace an existing `.claude/commands` directory symlink without prompting. |

### What gets linked

**`.github/`** (directory symlinks):

```
.github/agents  →  <agents_dir>
.github/prompts →  <prompts_dir>
.github/skills  →  <skills_dir>
```

**`.claude/`** (directory symlinks for agents and skills):

```
.claude/agents  →  <agents_dir>
.claude/skills  →  <skills_dir>
```

**`.claude/commands/`** (real directory with per-file symlinks):

```
.claude/commands/take-issue.md         →  ../../.uio/prompts/take-issue.prompt.md
.claude/commands/check-api-contract.md →  ../../.uio/prompts/check-api-contract.prompt.md
```

Running `uio link` a second time is a no-op. Adding or deleting a prompt file and re-running `uio link` adds or removes the corresponding symlink in `.claude/commands/`.

If `.claude/commands` already exists as a directory symlink (legacy setup), `uio link` will prompt to replace it with a real directory. Pass `--force` to replace without prompting.

---

## `uio mcp`

### `uio mcp init`

Scaffolds an MCP configuration file for Claude Code or VS Code, populated from the `[mcp.<name>]` server definitions in `uio.toml`. Secret values are never written to disk:

- For `--for claude`: `env_keys` become `${KEY_NAME}` env var references read from the environment at startup.
- For `--for vscode`: `env_keys` become `${input:key-name}` prompt references backed by a VS Code `inputs` block (`promptString`, `password: true`) — VS Code prompts the user to enter each secret at startup.

Declare the servers you want to expose in `uio.toml` first:

```toml
[mcp.github]
command  = "github-mcp-server stdio"
env_keys = ["GITHUB_PERSONAL_ACCESS_TOKEN"]
```

Then generate the platform config:

```bash
uio mcp init --for claude                 # writes .mcp.json
uio mcp init --for vscode                 # writes .vscode/mcp.json
uio mcp init --for claude --global        # merges into ~/.claude/settings.json
uio mcp init --for claude --force         # overwrites an existing .mcp.json
uio mcp init --for vscode --dry-run       # print target path without writing
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--for` | `claude\|vscode` | — | **Required.** Target platform. `claude` writes `.mcp.json`; `vscode` writes `.vscode/mcp.json`. |
| `--global` | flag | off | *(claude only)* Merge server entries into `~/.claude/settings.json` instead of writing a project-level `.mcp.json`. |
| `--force` | flag | off | Overwrite the target file (or existing `mcpServers.<name>` entry when `--global`) if it already exists. |
| `--dry-run` | flag | off | Print the target path without writing any files. |

Exit code: 0 on success, 1 if no `[mcp.*]` sections are found in `uio.toml`.

`.mcp.json` is added to `.gitignore` automatically by `uio init` if a `.gitignore` already exists, because secret references vary per developer.

See [MCP Integration](08-mcp.md) for full context on configuring and using MCP servers.

---

## `uio memory`

### `uio memory list`

Lists all memory files from `.uio/memory/*.memory.md` with their name, scope, and estimated body size in tokens.

Output columns: NAME, SCOPE, TOKENS

```bash
uio memory list
```

### `uio memory view <name>`

Prints the full body of the named memory file to stdout.

`NAME` is the value of the `name` frontmatter field (or the file stem if the field is absent).

```bash
uio memory view my-context
```

Exit code: 0 on success, 1 if the named memory file is not found.

### `uio memory clear [--session]`

Truncates memory file bodies. Without `--session`, clears ALL memory files (both project-scoped and session-scoped). With `--session`, clears only session-scoped memory files.

```bash
uio memory clear            # clear all memory files
uio memory clear --session  # clear only session-scoped files
```

| Flag | Description |
|---|---|
| `--session` | Clear only memory files with `scope: session` in their frontmatter (default: clear all). |

---

## `uio validate`

Parses all definition files in the configured directories (agents, skills, prompts, and workflows) and checks required frontmatter fields. Warns on unrecognised keys.

Standard validation also warns on heading format issues, unresolved skill references, and missing skill interface sections. `--strict` additionally enables stopping-criteria detection.

```bash
uio validate
uio validate --strict
```

| Flag | Description |
|---|---|
| `--strict` | Enable opt-in stopping-criteria detection (checks that agents include explicit stopping language) |

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
eval "$(uio completion bash)"                        # bash
eval "$(uio completion zsh)"                         # zsh
uio completion fish | source                         # fish
uio completion pwsh | Out-String | Invoke-Expression # PowerShell
```

To persist PowerShell completion, add the line to your `$PROFILE`:

```powershell
Add-Content $PROFILE "`nuio completion pwsh | Out-String | Invoke-Expression"
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

**Setting variables on Windows (PowerShell):**

```powershell
$env:GEMINI_API_KEY = "your-key"
$env:GITHUB_PERSONAL_ACCESS_TOKEN = "ghp_..."
```

To persist across sessions: `[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your-key", "User")`

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error (file not found, validation failed, network error, provider failed) |

All errors are written to stderr. Normal output goes to stdout, making it safe to pipe `uio cost --json`, `uio agent list`, etc.
