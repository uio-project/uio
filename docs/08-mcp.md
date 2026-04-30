# MCP Integration

## What is MCP?

**Model Context Protocol (MCP)** is a standardised stdio JSON-RPC 2.0 protocol for exposing typed tools to LLMs. An MCP server is a process that speaks this protocol and exports a set of tools — each with a name, description, and JSON Schema for its parameters.

uio implements the **client side**: it optionally spawns an MCP server subprocess and registers its tools alongside the built-in `run_command` tool. The agent sees all tools in the same schema and can call any of them.

uio itself does not implement any MCP tools — it delegates entirely to the server process.

---

## GitHub MCP server

The most common use case is the official GitHub MCP server (`@github/github-mcp-server`), which exposes ~30 GitHub API operations as typed tools: create/list issues, read file contents, list pull requests, manage branches, and more.

Using the GitHub MCP server instead of `gh` CLI shell commands gives the agent:
- Typed, structured JSON responses (no shell output parsing)
- Paginated results without custom shell gymnastics
- Full GitHub API coverage

When MCP tools are available, uio injects a preamble into the system prompt advising the agent to prefer them over `gh` CLI equivalents.

---

## Prerequisites

- **Node.js** (any recent LTS version) and **npx**. The MCP server is launched as `npx -y @github/github-mcp-server stdio`.
- A GitHub personal access token with the scopes your agent needs.

---

## Enabling GitHub MCP

Set either of these environment variables:

```bash
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
# or
export GITHUB_TOKEN=ghp_your_token_here
```

uio checks both; `GITHUB_PERSONAL_ACCESS_TOKEN` takes precedence. When the token is set, the GitHub MCP server starts automatically on every `agent run` and `skill run` (unless `--no-mcp` is passed).

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

By default, the server is launched as:

```
npx -y @github/github-mcp-server stdio
```

Override via `uio.toml` (preferred):

```toml
[mcp.github]
command = "bun x @github/github-mcp-server@1.2.0 stdio"
```

Or via the `MCP_GITHUB_COMMAND` environment variable (applies only to the backwards-compat auto-start path, i.e. when `[mcp.github]` is absent from `uio.toml`):

```bash
export MCP_GITHUB_COMMAND="bun x @github/github-mcp-server stdio"
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
command = "npx -y @github/github-mcp-server stdio"

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

**Duplicate server names** are not possible via `uio.toml` (TOML forbids duplicate keys). If `make_mcp_clients` is called programmatically with a dict that happens to have collisions, the first entry wins and subsequent ones are silently skipped.

---

## Troubleshooting

**`[mcp] Warning: could not start GitHub MCP server: ...`**

This warning is printed to stderr when the server fails to start. The run continues without MCP tools. Common causes:

- `npx` not found — install Node.js
- Token is invalid or expired — regenerate it at GitHub
- Node.js version is too old — upgrade to LTS (18+)

**The agent keeps using `gh` CLI even though MCP is enabled**

The model chooses which tools to call. The preamble advises it to prefer MCP tools but does not enforce it. If the agent consistently uses `gh` CLI, consider adding an explicit instruction to the agent's body: "Use MCP tools (`mcp__github__*`) for all GitHub operations."

**`Unknown tool: mcp__github__some_tool`**

The server was not started (either `--no-mcp` was passed or the token was missing). Verify with `uio config show`.
