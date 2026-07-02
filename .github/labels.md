# Label & issue-type taxonomy

This document is the human-readable companion to
[`labels.yml`](labels.yml) (the machine-readable source of truth synced to the
repo by [`workflows/labels-sync.yml`](workflows/labels-sync.yml)).

## Types vs. labels

The GitHub **issue type** (Epic / Feature / Task / Spike / Bug) is the
authoritative answer to *what kind of work this is*. Labels are secondary and
serve routing and workflow, not classification.

| Issue type | Mirror label | Meaning |
|------------|--------------|---------|
| Epic | `epic` | Multi-issue initiative tracked via sub-issues |
| Feature | `enhancement` | New capability or request (uses the existing `enhancement` label) |
| Task | `task` | Specific, scoped work including chores and docs |
| Spike | `spike` | Time-boxed investigation; does not ship directly |
| Bug | `bug` | Unexpected or incorrect behaviour |

> The **Feature** type maps to the pre-existing `enhancement` label rather than a
> new `feature` label, to avoid relabelling existing issues.

Issue templates apply only the *label* — set the matching issue **type** (a
separate GitHub field) when triaging. Org-level issue types must be enabled once
in the organization settings; see
[`docs/runbooks/github-project-setup.md`](../docs/runbooks/github-project-setup.md).

## Component labels (routing)

`component:*` labels route work to a subsystem. On pull requests they are
**applied automatically** by [`labeler.yml`](labeler.yml) based on changed paths,
mirroring the conventional-commit scopes in
[`CONTRIBUTING.md`](../CONTRIBUTING.md). Apply them manually on issues during
triage.

| Label | Subsystem |
|-------|-----------|
| `component:cli` | `uio/cli` |
| `component:core` | `uio/core` |
| `component:providers` | `uio/providers` |
| `component:registry` | `uio/registry` |
| `component:schema` | `uio/schema` |
| `component:agents` | `definitions/` |
| `component:docs` | docs and markdown |
| `component:ci` | CI, workflows, build config |
| `component:serve` | serve daemon and event triggers (`uio/serve`, planned — see [roadmap](../docs/21-roadmap.md)) |
| `component:fleet` | fleet / clustered operation (`uio/fleet`, planned) |
| `component:eval` | definition eval framework (`uio/eval`, planned) |

## Meta labels

| Label | Use |
|-------|-----|
| `backlog` | Unscheduled work — no milestone assigned |
| `needs-info` | Blocked pending more information from the reporter |
| `ai-governance` | AI agent governance, identity, and policy (see [`docs/governance.md`](../docs/governance.md)) |
| `blocked` | Blocked on an external dependency |
| `good first issue`, `help wanted` | Contribution routing |
| `dependencies`, `github-actions` | Applied by Dependabot |
| `documentation`, `refactor` | Nature-of-change hints (often mirror PR scopes) |
| `duplicate`, `invalid`, `wontfix`, `question` | Standard triage outcomes |

## Changing labels

Edit [`labels.yml`](labels.yml) and merge to `main`; the sync workflow creates or
updates labels automatically. The workflow does **not** delete labels missing
from the file (`skip-delete: true`), so removing a label is a manual step.
