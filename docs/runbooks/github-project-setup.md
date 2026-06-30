# Runbook — Project & Milestone Setup

> Documents the GitHub-native project-management conventions for
> `uio-project/uio`: milestones, the org Project board, issue types, and the
> label taxonomy. Most of this state **is** now version-controlled and
> reconciled automatically:
>
> - **Labels** — [`.github/labels.yml`](../../.github/labels.yml), synced by
>   [`labels-sync.yml`](../../.github/workflows/labels-sync.yml).
> - **Issue types, milestones, board fields** —
>   [`.github/project.yml`](../../.github/project.yml), reconciled by
>   [`project-sync.yml`](../../.github/workflows/project-sync.yml) (which runs
>   [`scripts/project-sync.sh`](../../scripts/project-sync.sh)).
>
> Only a small residue (board **views** and the **auto-add** workflow) is not
> exposed by the GitHub API and stays manual — see [Project board](#project-board).

---

## Work organization: two axes

Work is organized along two independent axes:

- **Phase (milestone)** — *when* the work happens.
- **Epic** — *which initiative* it belongs to (cross-cutting, long-lived,
  tracked via sub-issues).

A single issue can sit on both axes at once: assigned to a milestone *and*
linked under an epic.

## Declarative reconciler

Issue types, milestones, and the board's custom fields are declared in
[`.github/project.yml`](../../.github/project.yml) and reconciled to GitHub by
the **Project sync** workflow (push to `main` touching `project.yml`, or
**Actions → Project sync → Run workflow**). To preview locally:

```bash
bash scripts/project-sync.sh --dry-run   # show planned changes, mutate nothing
bash scripts/project-sync.sh             # apply
```

The reconciler is idempotent and check-existence-first: it creates what is
missing and patches drifted milestones; it never deletes.

**Auth.** Org issue types and the org Project board are organization-level
objects that the built-in `GITHUB_TOKEN` cannot write, so the workflow uses a
maintainer **`PROJECT_ADMIN_TOKEN`** secret — a PAT with `admin:org`, `project`,
and `repo` scopes. If the secret is unset the workflow exits cleanly with a
warning rather than failing. Locally, an authenticated `gh` with the same scopes
is sufficient.

## Milestones

Milestones answer *when* work happens and are declared under `milestones:` in
`project.yml`. The `M1–M7` phases tracked the now-complete GitHub-App-identity
initiative and are retained in a **closed** state for history. Live work uses the
release-themed milestones (`v0.2 — Stability & DX`, `v0.3 — Editor & CI
integration`, `v0.4 — Event-driven automation`, `v1.0`), or the `backlog` label
when unscheduled. Add or retire a milestone by editing `project.yml`.

## Organization issue types

Issue **types** (Epic / Feature / Task / Spike / Bug) are an organization-level
feature, declared under `issue_types:` in `project.yml` and ensured by the
reconciler. The type is **authoritative** for the kind of work; the mirror label
(`epic`/`task`/`spike`/`bug`, plus `enhancement` for Feature) exists for
filtering and is applied by the issue templates. Set the type on every new issue
during triage (see
[Contributing — triaging issues](../../CONTRIBUTING.md#triaging-issues)).

> If the `POST /orgs/{org}/issue-types` API is unavailable in your environment,
> enable the missing types once via org **Settings → Planning → Issue types**;
> the reconciler then no-ops over them.

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

A single **organization-level** Project (`uio 1.0`) holds all work. Its custom
**fields** are declared under `project.fields` in `project.yml` and created by
the reconciler:

- **Effort** — size estimate; single-select T-shirt scale `S` / `M` / `L` / `XL`.
- **Order** — manual priority ranking.
- **Start date / Target date** — timeline positioning for the Roadmap view.

(The built-in **Status** field — Todo / In Progress / Done — already exists and
is not managed by the spec.)

### Manual residue (no GitHub API)

The GitHub ProjectV2 API cannot create board **views** or configure the
**auto-add** workflow, so these stay manual one-time steps (tracked as a
`backlog` follow-up). Configure them in the project's UI:

| View | Layout | Purpose |
|---|---|---|
| Roadmap | Timeline | Scheduling across Start/Target dates |
| Board | Kanban (Todo → In Progress → Done) | Day-to-day workflow |
| Open Items | Table | Triage and bulk editing |

Then enable **⚙ → Workflows → Auto-add to project** so new issues and PRs appear
on the board without manual curation.

### Reusing this setup (project templates)

Because views and auto-add can't be declared in `project.yml` yet (#291), the
supported way to reuse this board layout for a **new** project is GitHub's
built-in **project templates**:

1. With the views and custom fields configured once, open the project →
   **⋯ → Settings** and toggle **"Make template"** (org-owned projects only).
2. Create the new project via **New project → "Start from a template"** and pick
   this one.

A template copies **views, custom fields, and configured workflows** — but **not
the items**. The **auto-add** workflow targets a specific project, so re-verify
or re-enable it in each project created from the template. The declarative layer
(`project.yml` + `project-sync`) still handles issue types, milestones, and
fields on top, so a new repo only needs its own `project.yml` and the
`PROJECT_ADMIN_TOKEN` secret.

## Triage checklist

Every new issue (see [Contributing](../../CONTRIBUTING.md#triaging-issues)):

- [ ] Set the issue **type** (Epic / Feature / Task / Spike / Bug)
- [ ] Apply `component:*` label(s)
- [ ] Assign a milestone **or** apply `backlog`
- [ ] Link the epic parent if applicable (`Parent issue: #N`)
- [ ] Set board **Status** to `Todo`
