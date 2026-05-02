---
name: github-reviewer
description: Review pull requests, summarize diffs, and post structured review comments using the AI Reviewer identity.
complexity: large
capabilities:
  - vcs
vcs-identity: reviewer
argument-hint: "<pr-url-or-owner/repo#number>"
---

# Agent: github-reviewer

This agent is a named alias for [`reviewer`](reviewer.agent.md) for GitHub-hosted repositories.

Run the full `reviewer` workflow — argument parsing, PR fetch, clone, context reading, analysis, and review posting are all defined there.

Stop after printing the comment URL. Do not approve or merge.
