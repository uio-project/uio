---
name: github-post-review
description: Post a review comment to a GitHub pull request.
---

# Skill: github-post-review

## Input

- `owner/repo` — repository containing the pull request (required)
- `pr-number` — pull request number to comment on (required)
- `body` — Markdown review text to post (required)

## Output

The review is posted as a PR comment. Returns `$comment_url`.

## Steps

### 1. Post the comment

Use the GitHub MCP tool if available:

```
mcp__mcp-github__add_issue_comment  owner=<owner>  repo=<repo>  issue_number=<pr-number>  body=<body>
```

Fall back to the `gh` CLI when unavailable:

```bash
gh pr comment <pr-number> --repo <owner>/<repo> --body "<body>"
```

### 2. Return the comment URL

Confirm the comment was posted and return `$comment_url` to the calling agent.
Stop and report an error if the comment could not be posted.
