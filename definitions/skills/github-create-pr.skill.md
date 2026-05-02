---
name: github-create-pr
description: Push a branch to origin and open a pull request on GitHub.
---

# Skill: github-create-pr

## Input

- `owner/repo` — repository to open the PR against (required)
- `base-branch` — branch the PR targets (required)
- `head-branch` — branch containing the changes (required)
- `title` — PR title (required)
- `body` — PR body in Markdown (required)
- `work-dir` — local path to the cloned repository (required)
- `closes-issue` — issue number to close when the PR merges (optional)

## Output

The branch is pushed to `origin` and a pull request is open. Returns `$pr_url`.

## Steps

### 1. Push the branch

```bash
git -C <work-dir> push origin <head-branch>
```

If the push fails because the remote branch already exists and has diverged, rebase first:

```bash
git -C <work-dir> fetch origin <head-branch>
git -C <work-dir> rebase origin/<head-branch>
git -C <work-dir> push origin <head-branch>
```

Stop and report an error if the push fails for any other reason.

### 2. Create the pull request

Append `\n\nCloses #<closes-issue>` to `<body>` when `closes-issue` is provided.

Use the GitHub MCP tool if available:

```
mcp__mcp-github__create_pull_request  owner=<owner>  repo=<repo>  title=<title>  body=<body>  head=<head-branch>  base=<base-branch>
```

Fall back to the `gh` CLI when unavailable:

```bash
gh pr create --repo <owner>/<repo> --base <base-branch> --head <head-branch> \
    --title "<title>" --body "<body>"
```

### 3. Verify and return

Confirm the PR exists. Use the GitHub MCP tool if available, otherwise:

```bash
gh pr view <pr-number> --repo <owner>/<repo>
```

Return `$pr_url` to the calling agent. Stop and report an error if the PR was not created.
