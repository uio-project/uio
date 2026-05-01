# MCP Integration

## What is MCP?

**Model Context Protocol (MCP)** is a standardised stdio JSON-RPC 2.0 protocol for exposing typed tools to LLMs. An MCP server is a process that speaks this protocol and exports a set of tools — each with a name, description, and JSON Schema for its parameters.

uio implements the **client side**: it optionally spawns an MCP server subprocess and registers its tools alongside the built-in `run_command` tool. The agent sees all tools in the same schema and can call any of them.

uio itself does not implement any MCP tools — it delegates entirely to the server process.

---

## GitHub MCP server

The most common use case is the official GitHub MCP server ([github/github-mcp-server](https://github.com/github/github-mcp-server)), which exposes ~30 GitHub API operations as typed tools: create/list issues, read file contents, list pull requests, manage branches, and more.

Using the GitHub MCP server instead of `gh` CLI shell commands gives the agent:
- Typed, structured JSON responses (no shell output parsing)
- Paginated results without custom shell gymnastics
- Full GitHub API coverage

When MCP tools are available, uio injects a preamble into the system prompt advising the agent to prefer them over `gh` CLI equivalents.

---

## Installing the GitHub MCP server

uio probes for the best available command in this order:

| Priority | Method | Install | Notes |
|---|---|---|---|
| **1** | **gh extension** (recommended) | `gh extension install github/gh-mcp` | Uses `gh`'s ambient auth; no extra token needed. **Skipped for App identity agents** — see below. |
| **2** | Standalone binary | Download from [GitHub Releases](https://github.com/github/github-mcp-server/releases) | Place `github-mcp-server` on `$PATH`. Accepts App installation tokens. |
| **3** | Community npm | `npx @modelcontextprotocol/server-github` | Accepts App installation tokens; widely available. |

**Recommended setup (one-time):**

```bash
# Install the gh extension
gh extension install github/gh-mcp

# Verify it starts and lists tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | gh mcp server | head -c 500
```

---

## Prerequisites

- **`gh` CLI** (recommended) — install from <https://cli.github.com>. Run `gh auth login` once.
- *Or* **Node.js + npx** (any recent LTS) if using the community npm fallback.
- A GitHub token with the scopes your agent needs (handled automatically when using `gh`).

---

## Enabling GitHub MCP

Set any of these environment variables (checked in priority order):

```bash
export GH_TOKEN=ghp_your_token_here              # highest priority (set by App identity agents)
# or
export GITHUB_TOKEN=ghp_your_token_here
# or
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
```

uio checks `GH_TOKEN` first, then `GITHUB_TOKEN`, then `GITHUB_PERSONAL_ACCESS_TOKEN`. When any token is set, the GitHub MCP server starts automatically on every `agent run` and `skill run` (unless `--no-mcp` is passed). The selected token is exported under all three names in the MCP server's child process, so any server implementation finds it.

Verify the setup:

```bash
uio config show
# MCP github  ✓ GITHUB_PERSONAL_ACCESS_TOKEN set
```

---

## Token scopes

Use a fine-grained personal access token scoped to the minimum permissions your agent needs:

| Agent task | Required scopes |
|---|---|
| Read issues and PRs | `issues: read`, `pull_requests: read` |
| Create issues or comments | `issues: write` |
| Read file contents | `contents: read` |
| Create or merge PRs | `pull_requests: write`, `contents: write` |

Granting more scopes than needed increases the blast radius of a mistake. Create a separate token per project or per agent role.

---

## Tool naming

All MCP tools are prefixed with `mcp__<server_name>__`. The GitHub server uses `mcp__github__`:

```
mcp__github__list_issues
mcp__github__create_issue
mcp__github__get_file_contents
mcp__github__list_pull_requests
mcp__github__create_pull_request
...
```

The prefix is added by `MCPClient.list_tools()` and removed transparently by `MCPClient.call_tool()` before forwarding the request to the server.

Agents do not need to know about the naming convention — the model sees the full tool list and calls tools by their prefixed name.

---

## Disabling MCP

To run without any MCP servers:

```bash
uio agent run my-agent --no-mcp
```

Use this when:
- The environment does not have Node.js or npx
- You want to test the agent's shell-only behaviour
- Network isolation requirements prevent spawning the servers
- The agent does not need any MCP tools

---

## Overriding the launch command

By default, uio probes for the best available command (see the priority table above). You can override this in `uio.toml` (preferred):

```toml
[mcp.github]
command = "gh mcp server"   # gh extension (recommended)
# command = "github-mcp-server stdio"  # standalone binary
# command = "npx -y @modelcontextprotocol/server-github"  # community npm
```

Or via the `MCP_GITHUB_COMMAND` environment variable (applies only to the backwards-compat auto-start path, i.e. when `[mcp.github]` is absent from `uio.toml`):

```bash
export MCP_GITHUB_COMMAND="gh mcp server"
```

---

## How the MCP client works (internals)

`uio/core/mcp.py` implements a minimal MCP stdio client:

1. **Spawn** — the server process is started with `subprocess.Popen` with stdin/stdout pipes. stderr is discarded.
2. **Handshake** — `initialize` RPC is sent with the uio client info; the server acknowledges with `initialized` notification.
3. **Tool discovery** — `tools/list` RPC returns the server's tool schemas. uio prefixes each name.
4. **Tool calls** — during the agent loop, when the model requests an MCP tool, `MCPClient.call_tool()` strips the prefix and sends a `tools/call` RPC. Text content from the response is joined and returned as a string.
5. **Shutdown** — `close()` closes the stdin pipe and terminates the process on session end.

Communication uses newline-delimited JSON. Each request includes an incrementing `id`; responses are matched by `id`. The client spins on `stdout.readline()` until the matching response arrives.

---

## Additional MCP servers

`uio` supports multiple MCP servers running simultaneously. Configure each one as a `[mcp.<name>]` section in `uio.toml`:

```toml
[mcp.github]
command = "gh mcp server"

[mcp.filesystem]
command = "npx -y @modelcontextprotocol/server-filesystem /workspace"

[mcp.fetch]
command = "npx -y @modelcontextprotocol/server-fetch"

[mcp.memory]
command = "npx -y @modelcontextprotocol/server-memory"
```

The `[mcp.<name>]` key becomes the `server_name` prefix. Tools are exposed to the LLM as `mcp__filesystem__read_file`, `mcp__fetch__fetch`, etc.

If a server fails to start, uio prints a warning and continues without it — the remaining servers and `run_command` remain available.

**Backwards compatibility:** If no `[mcp.github]` section is present in `uio.toml`, uio auto-starts the GitHub server whenever `GITHUB_PERSONAL_ACCESS_TOKEN` is set. Existing setups that rely on the token-based auto-start require no config changes.

---

## Git MCP server

`@modelcontextprotocol/server-git` exposes local Git repository operations as typed JSON tools. Agents that frequently call `run_command` with `git log`, `git diff`, or `git blame` get structured responses instead of raw shell output — fewer parse errors and fewer context tokens consumed.

### Tools exposed

| Tool | Description |
|---|---|
| `mcp__git__git_log` | Structured commit history — author, date, message, sha |
| `mcp__git__git_diff` | Typed diff between refs or against the working tree |
| `mcp__git__git_show` | File content at a specific commit |
| `mcp__git__git_blame` | Per-line attribution |
| `mcp__git__git_status` | Working tree status |
| `mcp__git__git_branch` | List or create branches |
| `mcp__git__git_commit` | Stage and commit changes |

### Configuration

The server requires a `path` argument — the absolute path to the repository root inside the container:

```toml
[mcp.git]
command = "npx -y @modelcontextprotocol/server-git /workspace"
```

`/workspace` is the default mount point in the uio container image. Adjust the path if you mount your repository elsewhere.

`server-git` has no token requirement and starts unconditionally when `[mcp.git]` is present in `uio.toml`.

**Duplicate server names** are not possible via `uio.toml` (TOML forbids duplicate keys). If `make_mcp_clients` is called programmatically with a dict that happens to have collisions, the first entry wins and subsequent ones are silently skipped.

---

## Sequential Thinking MCP server

`@modelcontextprotocol/server-sequential-thinking` externalises an agent's reasoning process as discrete, revisable tool calls. Instead of reasoning implicitly inside a single model response, the agent emits each thought step as a `sequentialthinking` tool call — making the chain visible in the uio run output and cost ledger.

This is most useful for planning and review agents where auditability of the reasoning chain matters, and for high-iteration tool-use loops where the model would otherwise skip steps.

### Tool exposed

The server exposes a single tool: `mcp__sequential-thinking__sequentialthinking`

| Parameter | Type | Required | Description |
|---|---|---|---|
| `thought` | string | yes | The current reasoning step |
| `nextThoughtNeeded` | boolean | yes | Whether more steps are needed |
| `thoughtNumber` | integer | yes | Step index (1-based) |
| `totalThoughts` | integer | yes | Estimated total steps |
| `isRevision` | boolean | no | Whether this step revises a prior one |
| `revisesThought` | integer | no | Index of the step being revised |

### Configuration

Add as a plugin entry in `uio.toml`:

```toml
[[mcp.plugins]]
name    = "sequential-thinking"
type    = "think"
command = "npx -y @modelcontextprotocol/server-sequential-thinking"
```

The server has no token requirement and starts unconditionally when the entry is present.

### Usage pattern for planning agents

Include an explicit instruction in the agent body to drive the reasoning chain before taking action:

```markdown
Before creating any issues or making any changes:
1. Use the `mcp__sequential-thinking__sequentialthinking` tool to think through the problem.
   - Break the task into steps (set totalThoughts to your estimate).
   - Revise earlier steps if new information changes your approach.
   - Set nextThoughtNeeded to false only when you have a complete plan.
2. Execute the plan produced by your reasoning chain.
```

Reasoning steps appear in the run output like any other tool call, so they are captured in the cost ledger and visible in CI logs.

---

## Troubleshooting

**`[mcp] Warning: could not start GitHub MCP server: ...`**

This warning is printed to stderr when the server fails to start. The run continues without MCP tools. Common causes:

- `gh` extension not installed — run `gh extension install github/gh-mcp`
- `gh` not authenticated — run `gh auth login`
- `npx` not found (community npm fallback) — install Node.js
- Token is invalid or expired — regenerate it at GitHub

**App installation tokens and `gh mcp server`**

Identity agents (Planner, Coder, Reviewer) authenticate with a short-lived GitHub App installation token (`ghs_…`). The `gh mcp server` extension validates the token type on startup and rejects App installation tokens — only user OAuth tokens and PATs are accepted.

uio automatically skips `gh mcp server` when an App identity token is detected and falls through to the standalone binary or community npm fallback, both of which accept App installation tokens as raw Bearer tokens.

If neither the standalone binary nor `npx` is available in your environment, set `MCP_GITHUB_COMMAND` to a working server invocation:

```bash
export MCP_GITHUB_COMMAND="npx -y @modelcontextprotocol/server-github"
```

Or configure it in `uio.toml` to apply permanently:

```toml
[mcp.github]
command = "npx -y @modelcontextprotocol/server-github"
```

**The agent keeps using `gh` CLI even though MCP is enabled**

The model chooses which tools to call. The preamble advises it to prefer MCP tools but does not enforce it. If the agent consistently uses `gh` CLI, consider adding an explicit instruction to the agent's body: "Use MCP tools (`mcp__github__*`) for all GitHub operations."

**`Unknown tool: mcp__github__some_tool`**

The server was not started (either `--no-mcp` was passed or the token was missing). Verify with `uio config show`.
