---
name: github-fetch-issue
description: Fetch issue title, body, and all comments from a GitHub repository.
---

# Skill: github-fetch-issue

## Input

- `owner/repo` — repository containing the issue (required)
- `issue-number` — issue number to fetch (required)

## Output

Structured issue data made available to the calling agent:

- `$issue_title` — issue title
- `$issue_body` — issue body text
- `$issue_comments` — ordered list of all comments (author, association, body, timestamp)

## Steps

### 1. Fetch issue body

Use the GitHub MCP tool if available:

```
mcp__mcp-github__issue_read  method=get  owner=<owner>  repo=<repo>  issue_number=<issue-number>
```

Fall back to the `gh` CLI when unavailable:

```bash
gh issue view <issue-number> --repo <owner>/<repo> --json number,title,body,author,createdAt
```

### 2. Fetch comments

Use the GitHub MCP tool if available:

```
mcp__mcp-github__issue_read  method=get_comments  owner=<owner>  repo=<repo>  issue_number=<issue-number>  perPage=100
```

If the response indicates more pages exist, repeat with `page=2`, `page=3`, … until all comments are retrieved.

Fall back to the `gh` CLI when unavailable:

```bash
gh issue view <issue-number> --repo <owner>/<repo> --comments --json comments
```

### 3. Return structured data

Expose the fetched data as `$issue_title`, `$issue_body`, and `$issue_comments` for the calling agent. Stop and report an error if the issue does not exist or the request fails.
