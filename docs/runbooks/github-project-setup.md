# Runbook — Project & Milestone Setup

> Documents the GitHub-native project-management conventions for
> `uio-project/uio`: milestones, the org Project board, issue types, and the
> label taxonomy. Most of this is GitHub-UI state that cannot be version-
> controlled, so this runbook is the source of truth for *how it should be set
> up*. The label set itself **is** versioned — see
> [`.github/labels.yml`](../../.github/labels.yml) and
> [`.github/labels.md`](../../.github/labels.md).

---

## Work organization: two axes

Work is organized along two independent axes:

- **Phase (milestone)** — *when* the work happens.
- **Epic** — *which initiative* it belongs to (cross-cutting, long-lived,
  tracked via sub-issues).

A single issue can sit on both axes at once: assigned to a milestone *and*
linked under an epic.

## Milestones (M1–M7)

The repository already uses a phase-based milestone scheme. Assign every
scheduled issue to one of these; apply the `backlog` label to anything
unscheduled.

| Milestone | Phase |
|---|---|
| `M1: Discovery & Design` | Initial design and research |
| `M2: GitHub App Provisioning` | Standing up the AI App identities |
| `M3: uio Platform Engineering` | Core CLI / platform work |
| `M4: Agent Definitions for Registry` | Shipping reusable agent definitions |
| `M5: Governance & Security` | Governance, permissions, runbooks |
| `M6: Pilot & Credential Migration` | Pilot rollout and credential migration |
| `M7: Evaluation & Expansion` | Evaluation and broader rollout |

> **Gap to close:** open issues are not currently assigned to milestones. Triage
> the existing backlog so each open issue has a milestone or the `backlog` label
> (tracked under epic #286).

## Enable organization issue types (one-time)

Issue **types** (Epic / Feature / Task / Spike / Bug) are an organization-level
feature and must be enabled once before they can be set on issues:

1. Org **Settings → Planning → Issue types**.
2. Ensure the five types exist: Epic, Feature, Task, Spike, Bug.
3. Thereafter, set the type on every new issue during triage (see
   [Contributing — triaging issues](../../CONTRIBUTING.md#triaging-issues)).

The type is **authoritative** for the kind of work; the mirror label
(`epic`/`task`/`spike`/`bug`, plus `enhancement` for Feature) exists for
filtering and is applied by the issue templates.

## Labels

Labels are defined in [`.github/labels.yml`](../../.github/labels.yml) and synced
to the repo automatically by
[`.github/workflows/labels-sync.yml`](../../.github/workflows/labels-sync.yml) on
merge to `main` (or via **Actions → Labels sync → Run workflow**). After the
first sync, confirm with `gh label list --repo uio-project/uio`. The full
taxonomy and policy are documented in [`.github/labels.md`](../../.github/labels.md).

`component:*` labels are applied to PRs automatically by
[`.github/labeler.yml`](../../.github/labeler.yml); apply them to issues manually
during triage.

## Project board

Create a single **organization-level** Project with three views over the same
items:

| View | Layout | Purpose |
|---|---|---|
| Roadmap | Timeline | Scheduling across Start/Target dates |
| Board | Kanban (Todo → In Progress → Done) | Day-to-day workflow |
| Open Items | Table | Triage and bulk editing |

Fields to define **at creation** (defining them later is the lesson learned the
hard way):

- **Status** — Kanban column (Todo / In Progress / Done).
- **Effort** — size estimate; define the options up front. Recommended T-shirt
  scale: `S`, `M`, `L`, `XL`.
- **Order** — manual priority ranking.
- **Start date / Target date** — timeline positioning for the Roadmap view.

Enable the **Auto-add workflow** at creation so new issues and PRs appear on the
board without manual curation.

## Triage checklist

Every new issue (see [Contributing](../../CONTRIBUTING.md#triaging-issues)):

- [ ] Set the issue **type** (Epic / Feature / Task / Spike / Bug)
- [ ] Apply `component:*` label(s)
- [ ] Assign a milestone **or** apply `backlog`
- [ ] Link the epic parent if applicable (`Parent issue: #N`)
- [ ] Set board **Status** to `Todo`
