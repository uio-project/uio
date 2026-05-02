# Claude Code Guidance

## Checking for MCP tools

Before using a CLI fallback (`gh`, `git`, etc.), use `ToolSearch` to check
whether a matching MCP tool is available in the current session:

```
ToolSearch("github issue comment")   # find GitHub issue tools
ToolSearch("git log blame")          # find git MCP tools
ToolSearch("select:get_issue,add_issue_comment")  # load specific tools by name
```

If `ToolSearch` returns a matching tool, load its schema and use it. If no match
is returned, fall back to the CLI.

## MCP tool naming in VS Code

VS Code exposes MCP tools **without** the `mcp__<server>__` prefix that the uio
runtime uses. The same GitHub tool appears as:

- `mcp__github__get_issue` in uio
- `get_issue` in VS Code

Search by capability keyword, not by full prefixed name, so the lookup works in
both environments.

## GitHub MCP server availability

`.vscode/mcp.json` is VS Code's MCP configuration for the Copilot extension —
it is **not** read by Claude Code. Claude Code loads MCP servers from:

- `.mcp.json` at the project root (project-scoped)
- `~/.claude/settings.json` under `mcpServers` (global)

Neither exists in this project yet. To enable the GitHub MCP server for Claude
Code, create `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "github": {
      "command": "github-mcp-server",
      "args": ["stdio"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "<your-pat>"
      }
    }
  }
}
```

Until that file exists, `ToolSearch` will not find any GitHub MCP tools and the
`gh` CLI fallback is the correct path.

## MCP tool path restrictions

The MCP git and filesystem servers in this environment enforce an allowed-paths
allowlist restricted to the workspace root (e.g. `/home/john/src/uio`). Any
operation on a path outside the workspace — including `/tmp` — will fail with
"Access denied / outside allowed repository".

Agent clone workspaces must therefore be placed under `<workspace-root>/.tmp/`
rather than `/tmp/`. The `.tmp/` directory is git-ignored. Use this pattern for
the work dir:

```
<workspace-root>/.tmp/<repo>-<branch-slug>
```

## GitHub MCP write operations (temporary limitation)

`mcp__mcp-github__create_pull_request` and `mcp__mcp-github__issue_write`
currently return 403 in this environment due to token scope. This is temporary.
Until resolved, fall back to the `gh` CLI for PR creation and issue creation:

```bash
gh pr create --repo <owner>/<repo> ...
gh issue create --repo <owner>/<repo> ...
```

Read operations (`issue_read`, `pull_request_read`, etc.) work correctly.

## Running agent definitions directly

When a user asks to execute a workflow described in `definitions/agents/*.agent.md`,
run the workflow steps directly in the conversation rather than invoking
`uio agent run <name>` via Bash. The `uio` CLI spawns a new model instance;
running the steps here keeps the work in context and avoids double-billing.
