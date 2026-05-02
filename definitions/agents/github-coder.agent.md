---
name: github-coder
description: Create branches, apply AI-generated code changes, and open pull requests using the AI Coder identity.
complexity: large
capabilities:
  - vcs
vcs-identity: coder
argument-hint: "<change-description> | repo: <owner>/<repo> [| issue: <number>] [| branch: <name>] [| base: <branch>] [| workdir: <path>]"
---

# Agent: github-coder

This agent is a named alias for [`coder`](coder.agent.md) for GitHub-hosted repositories.

Run the full `coder` workflow — argument parsing, issue fetch, branch creation, code changes, quality checks, commit, and PR creation are all defined there.

Stop after printing the PR URL. Do not merge, approve, or request review.
