---
name: github-post-comment
description: Post a comment on a GitHub issue or pull request.
---

# Skill: github-post-comment

## Input

- `owner/repo` — repository containing the issue or PR (required)
- `number` — issue or PR number (required)
- `body` — comment body in Markdown (required)

## Output

The comment is posted. Returns `$comment_url`.

## Steps

### 1. Post the comment

Use the GitHub MCP tool if available:

```
mcp__mcp-github__add_issue_comment  owner=<owner>  repo=<repo>  issue_number=<number>  body=<body>
```

Fall back to the `gh` CLI when unavailable:

```bash
gh issue comment <number> --repo <owner>/<repo> --body "<body>"
```

GitHub treats pull requests as issues for commenting purposes, so the same tool and
command work for both.

### 2. Return

Confirm the comment was posted and return `$comment_url` to the calling agent. Stop
and report an error if posting fails.
