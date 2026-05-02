# Agent Guidance

## MCP tools vs CLI fallbacks

When executing a workflow that involves GitHub API operations, git operations, or
any other capability that may be exposed via an MCP server, **always check your
available tool list first** before falling back to a CLI command.

The correct order:

1. Search your available tools for one that matches the operation.
2. If found, use it — MCP tools return structured data and require no shell parsing.
3. If not found, fall back to the CLI equivalent (`gh`, `git`, etc.).

The agent definition files in `definitions/` follow this pattern explicitly:

> "use a GitHub MCP tool if available, otherwise: `gh ...`"

Do not skip step 1 and go straight to the CLI. The MCP server may not be running
in every environment, but you should verify before assuming it is absent.

## Tool availability varies by environment

MCP tool names and availability differ depending on where the agent runs:

- **uio runtime** — tools are prefixed: `mcp__github__get_issue`, `mcp__git__git_log`, etc.
- **VS Code / Claude Code** — tools are unprefixed: `get_issue`, `git_log`, etc.
- **Other environments** — tool names and availability are environment-specific.

Because of this, agent definitions should describe *intent* rather than hardcode
tool names. The model discovers the correct tool name from its tool list at runtime.

## Git operations always use the shell

`git clone`, `git pull`, `git checkout`, `git commit`, `git push` have no MCP
equivalent and must always run via shell commands (`run_command` in uio, `Bash`
in Claude Code). Commit operations that require a custom author identity
(`-c user.name=... -c user.email=...`) also require the shell; no git MCP tool
supports custom author flags.

## `git_create_branch` does not switch HEAD

`mcp__mcp-git__git_create_branch` (and its environment-specific equivalents)
creates the branch but leaves HEAD on the current branch. Always follow it with
an explicit checkout via shell:

```bash
git -C <work-dir> checkout <branch-name>
```

Skipping this step causes subsequent commits to land on the wrong branch.
