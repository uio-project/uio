# Project-management framework

uio uses a lightweight, GitHub-native project-management model. This page is the
single entry point that ties the pieces together; each section links to its
canonical, versioned source.

The guiding principle is **definition-as-code**: as much of the PM setup as the
GitHub API allows is declared in the repo and reconciled automatically, the same
way uio treats agents, skills, and labels.

## Classification: types and labels

The GitHub **issue type** (Epic / Feature / Task / Spike / Bug) is the
authoritative answer to *what kind of work this is*. Labels are secondary and
serve routing and workflow, not classification:

- **`component:*`** labels route work to a subsystem (`cli`, `core`, `providers`,
  `registry`, `schema`, `agents`, `docs`, `ci`). On PRs they are applied
  automatically by path ([`.github/labeler.yml`](../.github/labeler.yml)); on
  issues they are applied during triage.
- **Mirror labels** (`epic`, `task`, `spike`, `bug`; `enhancement` for Feature)
  exist for filtering and are set by the issue templates.
- **Meta labels** (`backlog`, `needs-info`, `blocked`, `ai-governance`, …) drive
  workflow.

The full taxonomy and policy live in [`.github/labels.md`](../.github/labels.md);
the label set itself is declared in [`.github/labels.yml`](../.github/labels.yml).

## Scheduling: milestones

Milestones answer *when* work happens. They are declared under `milestones:` in
[`.github/project.yml`](../.github/project.yml). The historical `M1–M7` phases
(the completed GitHub-App-identity initiative) are retained `closed`; live work
uses six release-themed milestones (`v0.2 — Stability & DX` through `v1.0`; see
the [roadmap](21-roadmap.md) for each milestone's theme), or the `backlog` label
when unscheduled.

## The board

A single org Project (`uio 1.0`) holds all work, with a `Status` kanban field plus
custom fields (`Effort`, `Start date`, `Target date`, `Order`) declared in
`project.yml`. Board **views** and the **auto-add** workflow are not exposed by
the GitHub API and are configured manually — see the
[project-setup runbook](runbooks/github-project-setup.md#manual-residue-no-github-api).

## Declarative reconciler

Issue types, milestones, and board fields are reconciled from `project.yml` by the
**Project sync** workflow
([`.github/workflows/project-sync.yml`](../.github/workflows/project-sync.yml) →
[`scripts/project-sync.sh`](../scripts/project-sync.sh)), mirroring how
[`labels-sync.yml`](../.github/workflows/labels-sync.yml) reconciles labels. It is
idempotent and never deletes. Org-level changes require a maintainer
`PROJECT_ADMIN_TOKEN` (see the
[permission matrix](github-permission-matrix.md)), deliberately outside the
least-privilege AI-agent identities. Preview changes with
`bash scripts/project-sync.sh --dry-run`.

## Triage

Every new issue is triaged per the checklist in
[CONTRIBUTING — triaging issues](../CONTRIBUTING.md#triaging-issues): set the
**type**, apply `component:*` label(s), assign a **milestone or `backlog`**, link
the **epic parent** if applicable, and set board **Status** to `Todo`. The
`planner` agent applies this taxonomy automatically when it files or triages
issues.

## Decision records

Non-obvious architectural or process decisions are recorded as dated entries in
[`docs/18-design-decisions.md`](18-design-decisions.md) — the pre-1.0,
lightweight alternative to formal RFCs.
