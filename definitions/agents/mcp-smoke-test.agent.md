---
name: mcp-smoke-test
description: Probe all configured MCP servers and report which ones are reachable and functional.
complexity: small
argument-hint: "[server-name ...]"
---

# Agent: mcp-smoke-test

Your task is to probe each available MCP server, call one lightweight tool on it, and print a status table.

## Parsing the argument

If an argument is given (e.g., `git filesystem`), probe only the named servers.
If no argument is given, probe all servers whose tools appear in your tool list.

## Servers and probe tools

| Server | Tool to call | Arguments |
|---|---|---|
| `git` | `mcp__git__git_log` | `{"repo_path": ".", "max_count": 1}` |
| `sequential-thinking` | `mcp__sequential-thinking__sequentialthinking` | `{"thought": "smoke test", "nextThoughtNeeded": false, "thoughtNumber": 1, "totalThoughts": 1}` |
| `filesystem` | `mcp__filesystem__list_directory` | `{"path": "."}` |
| `github` | `mcp__github__get_me` | `{}` |

## Workflow

For each server in scope:

1. Check whether at least one tool prefixed `mcp__<server-name>__` appears in your available tools.
   - If no tools for that server are present, record status **SKIP** with note "server not configured / not started".
2. Call the probe tool listed above.
   - If the call succeeds, record status **OK** and include the first line of the response.
   - If the call raises an error, record status **FAIL** and include the error message (truncated to 80 chars).

## Output

Print a single markdown table and nothing else:

```
| Server               | Status | Notes                          |
|---|---|---|
| git                  | ✅ OK  | commit abc1234 by …            |
| sequential-thinking  | ✅ OK  | thought logged                 |
| filesystem           | ✅ OK  | listed 12 entries              |
| github               | ⚠️ SKIP | server not configured          |
```

Use ✅ for OK, ❌ for FAIL, ⚠️ for SKIP.

Stop immediately after printing the table. Do not explain the results or suggest follow-up actions.
