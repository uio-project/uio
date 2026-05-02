---
name: github-create-issue
description: Create a new issue in a GitHub repository.
---

# Skill: github-create-issue

## Input

- `owner/repo` — repository to create the issue in (required)
- `title` — issue title (required)
- `body` — issue body in Markdown (required)
- `labels` — comma-separated list of labels to apply (optional)

## Output

The issue is created. Returns `$issue_url` and `$issue_number`.

## Steps

### 1. Create the issue

Use the GitHub MCP tool if available:

```
mcp__mcp-github__issue_write  method=create  owner=<owner>  repo=<repo>  title=<title>  body=<body>
```

Fall back to the `gh` CLI when unavailable:

```bash
gh issue create --repo <owner>/<repo> --title "<title>" --body "<body>"
```

If `labels` is provided, append `--label "<labels>"` to the CLI command or pass as a
parameter to the MCP tool.

### 2. Return

Confirm the issue was created and return `$issue_url` and `$issue_number` to the calling
agent. Stop and report an error if creation fails.
