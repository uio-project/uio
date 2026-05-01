# GitHub App Identities

uio supports dedicated GitHub App identities for agents that act on GitHub — separate
non-human service accounts for planning, coding, and reviewing work. Each identity has a
distinct permission scope, enforcing separation of duties at the GitHub App layer.

## The three identities

| Identity | Frontmatter value | Operations |
|---|---|---|
| AI Planner | `planner` | Create issues · Comment on issues and PRs · Summarize milestones |
| AI Coder | `coder` | Create branches · Commit code · Open pull requests |
| AI Reviewer | `reviewer` | Read diffs · Post structured review comments |

## Declaring an identity

Add `github-identity` to your agent's frontmatter:

```yaml
---
name: my-github-agent
description: An agent that opens pull requests.
github-identity: coder   # planner | coder | reviewer
capabilities:
  - terminal
  - vcs
---
```

uio obtains a short-lived GitHub App installation token before the agent loop starts and
sets `GH_TOKEN` — both the `gh` CLI and GitHub MCP server pick it up automatically.

## Further reading

| Document | What it covers |
|---|---|
| [GitHub identity inventory](github-identity-inventory.md) | Current-state survey of GitHub auth usage across uio definitions |
| [Permission matrix](github-permission-matrix.md) | Minimum permissions, explicit exclusions, and identity routing map |
| [Governance](governance.md) | Attribution standard, app ownership, quarterly review, change control, installation policy |
| [Provisioning — AI Planner](provisioning/ai-planner.md) | Step-by-step setup for the `uio-ai-planner` GitHub App |
| [Provisioning — AI Coder](provisioning/ai-coder.md) | Step-by-step setup for the `uio-ai-coder` GitHub App |
| [Provisioning — AI Reviewer](provisioning/ai-reviewer.md) | Step-by-step setup for the `uio-ai-reviewer` GitHub App |
| [Runbook — Audit](runbooks/github-app-audit.md) | Logging requirements and GitHub audit log review process |
| [Runbook — Incident response](runbooks/github-app-incident-response.md) | P1/P2/P3 incident tiers, 8-step response, post-mortem template |
| [Runbook — Credential rotation](runbooks/github-app-credential-rotation.md) | Zero-downtime private key rotation using dual-key overlap |
| [Runbook — Emergency disable](runbooks/github-app-emergency-disable.md) | Fast-path: suspend, delete key, or uninstall in under 2 minutes |
| [Runbook — Branch protection](runbooks/github-branch-protection.md) | Applied baseline, reconfiguration command, AI Coder bypass verification |
