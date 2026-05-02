---
name: github-fetch-pr
description: Fetch PR metadata and full diff from a GitHub pull request.
---

# Skill: github-fetch-pr

## Input

- `owner/repo` — repository containing the pull request (required)
- `pr-number` — pull request number to fetch (required)

## Output

Structured PR data made available to the calling agent:

- `$pr_title` — pull request title
- `$pr_body` — pull request description body
- `$pr_author` — login of the PR author
- `$pr_base_ref` — base branch name (target of the merge)
- `$pr_head_ref` — head branch name (source of the changes)
- `$pr_files` — list of changed files with additions and deletions per file
- `$pr_additions` — total lines added
- `$pr_deletions` — total lines deleted
- `$pr_diff` — full unified diff of all changes

## Steps

### 1. Fetch PR metadata

Use the GitHub MCP tool if available:

```
mcp__mcp-github__pull_request_read  method=get  owner=<owner>  repo=<repo>  pullNumber=<pr-number>
```

Fall back to the `gh` CLI when unavailable:

```bash
gh pr view <pr-number> --repo <owner>/<repo> \
    --json number,title,body,author,baseRefName,headRefName,files,additions,deletions
```

### 2. Fetch the full diff

Use the GitHub MCP tool if available:

```
mcp__mcp-github__pull_request_read  method=get_diff  owner=<owner>  repo=<repo>  pullNumber=<pr-number>
```

Fall back to the `gh` CLI when unavailable:

```bash
gh pr diff <pr-number> --repo <owner>/<repo>
```

For large PRs (>500 lines changed), focus on:
1. New or modified functions and their signatures
2. Error handling paths
3. Security-sensitive code (auth, input validation, SQL, shell commands)
4. Configuration and environment variable changes

### 3. Return structured data

Expose the fetched data as the output variables listed above for the calling agent.
Stop and report an error if the PR does not exist or the request fails.
If the diff is empty, report that the PR has no changes and stop.
