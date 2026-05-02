---
name: mcp-smoke-test
description: Probe all configured MCP servers and report which ones are reachable and functional.
complexity: small
argument-hint: "[server-name ...]"
---

# Agent: mcp-smoke-test

Your task is to probe each available MCP server and print a status table.

**Do not use `run_command` under any circumstances.** Only MCP tools may be called.
If a tool is not present in your tool list, record it as ⚠️ SKIP — do not simulate it with shell commands.

**Do not narrate or explain. Issue all probe tool calls in a single step, then immediately print the table.**

## Parsing the argument

If an argument is given (e.g., `git filesystem`), probe only the named servers.
If no argument is given, probe all four servers below.

## Step 1 — Call all probe tools simultaneously

In a single response, issue every applicable tool call at once (do not call them one at a time).

For each server, find the matching tool in your tool list — it may appear with or without the `mcp__<server>__` prefix depending on the runtime. If no matching tool exists, skip it.

| Server | Tool to find | Arguments |
|---|---|---|
| `git` | a tool named `git_log` | `{"repo_path": ".", "max_count": 1}` |
| `sequential-thinking` | a tool named `sequentialthinking` | `{"thought": "smoke test", "nextThoughtNeeded": false, "thoughtNumber": 1, "totalThoughts": 1}` |
| `filesystem` | a tool named `list_directory` | `{"path": "."}` |
| `github` | a tool named `search_repositories` | `{"query": "repo:jomkz/uio"}` |

## Step 2 — Print the table

After all tool results are in, print exactly this table and nothing else:

```
| Server               | Status  | Notes                          |
|---|---|---|
| git                  | ✅ OK   | commit 6916a28                 |
| sequential-thinking  | ✅ OK   | thought logged                 |
| filesystem           | ✅ OK   | listed 12 entries              |
| github               | ✅ OK   | jomkz/uio                     |
```

Use ✅ OK · ❌ FAIL · ⚠️ SKIP.

### Notes rules — enforce these strictly

| Server | Note format | Hard limit |
|---|---|---|
| `git` | `commit <7-char hash>` | Hash only — omit the commit message |
| `sequential-thinking` | `thought logged` | — |
| `filesystem` | `listed <N> entries` | — |
| `github` | `<full_name>` only | 20 chars max, no description |

Never include raw JSON, full sentences, URLs, or object literals in the Notes column.
