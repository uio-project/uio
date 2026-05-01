---
name: mcp-smoke-test
description: Probe all configured MCP servers and report which ones are reachable and functional.
complexity: small
argument-hint: "[server-name ...]"
---

# Agent: mcp-smoke-test

Your task is to probe each available MCP server and print a status table.

**Do not narrate or explain. Issue all probe tool calls in a single step, then immediately print the table.**

## Parsing the argument

If an argument is given (e.g., `git filesystem`), probe only the named servers.
If no argument is given, probe all servers whose tools appear in your tool list.

## Step 1 — Call all probe tools simultaneously

In a single response, issue every applicable tool call at once (do not call them one at a time):

| Server | Tool | Arguments |
|---|---|---|
| `git` | `mcp__git__git_log` | `{"repo_path": ".", "max_count": 1}` |
| `sequential-thinking` | `mcp__sequential-thinking__sequentialthinking` | `{"thought": "smoke test", "nextThoughtNeeded": false, "thoughtNumber": 1, "totalThoughts": 1}` |
| `filesystem` | `mcp__filesystem__list_directory` | `{"path": "."}` |
| `github` | `mcp__github__search_repositories` | `{"query": "repo:jomkz/uio"}` |

Skip any server whose tools are absent from your tool list — record it as ⚠️ SKIP in the table.

## Step 2 — Print the table

After all tool results are in, print exactly this table and nothing else:

```
| Server               | Status  | Notes                          |
|---|---|---|
| git                  | ✅ OK   | commit 6916a28                 |
| sequential-thinking  | ✅ OK   | thought logged                 |
| filesystem           | ✅ OK   | listed 12 entries              |
| github               | ✅ OK   | jomkz/uio — Universal I/O     |
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
