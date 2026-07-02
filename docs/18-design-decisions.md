# Design decisions

This page documents the rationale behind key design decisions in uio. It will grow as more decisions are recorded.

The narrative sections below capture larger decisions in prose. Smaller, dated
decisions are recorded in the [Decision log](#decision-log) using the format:

```
**YYYY-MM-DD — <Title> (<scope>, #<issue>).** <rationale>
```

This lightweight, dated log is the pre-1.0 alternative to heavyweight RFCs;
the planner and closer agents append to it when a change reflects a non-obvious
choice.

## Why Python?

uio's core bottleneck is waiting on LLM API responses and subprocess output — both are I/O-bound,
not CPU-bound, so a systems language offers no meaningful speed advantage. The codebase is oriented
around string manipulation, YAML/TOML parsing, and subprocess orchestration, which Python handles
idiomatically. The ecosystem for LLM SDKs, GitHub API clients, and AI tooling is also far richer
in Python.

## What about CLI startup time?

A compiled binary would start faster, but uio is a long-running orchestration tool, not a
tight feedback-loop CLI, so cold-start latency is rarely the pain point. If specific hot paths
(e.g. token estimation, file scanning) ever become bottlenecks, a targeted Rust extension via
PyO3 would be preferable to a full rewrite.

Python is well-matched to what uio actually does. uio's value is in its agent
definitions and workflow logic — the language that lets you iterate fastest on prompts, routing,
and integrations is the right one.

## Decision log

Newest first.

**2026-07-01 — Roadmap restructure: 1.0 after fleet; GitOps-on-a-queue cluster architecture; evals as CI artifacts (core, #296).**
Expanded the roadmap from four milestones to six and moved the 1.0 cut *after*
the server/cluster work: `v0.3` refocused as *Editor, CI & Evals*, `v0.4` as
*Trust & Observability*, with new `v0.5 — Serve & Events` (#261's home) and
`v0.6 — Fleet`. Rationale: serve/fleet churn public interfaces (run-record
schema, queue API, frontmatter keys), and pre-1.0 is the license to break them —
see [roadmap](21-roadmap.md). Three architectural commitments made:
(1) **Cluster backbone is a durable queue + GitOps fleet manifest** — stateless
`uio serve` workers on a pluggable queue (SQLite single-node, Postgres
`FOR UPDATE SKIP LOCKED` multi-node reference), desired state reconciled from a
git-hosted fleet manifest, fleet-wide budgets enforced via transactional cost
leases. Rejected: k8s-operator-first (abandons the pip/binary DX; duplicates in
etcd what git already provides) and coordinator-free gossip (hard budget caps
must be transactional, not eventually consistent — the guardrail is money).
(2) **Adaptation lands as PRs, never runtime mutation** — the routing tuner and
definition synthesis propose git diffs; the runtime never silently rewrites its
own behavior, preserving the audit-first property.
(3) **Evals as first-class CI artifacts** is the flagship differentiation bet:
`*.eval.md` suites beside definitions, golden-trace replay, semantic `uio diff`,
and (v0.6) eval-gated canary rollout of definitions across the fleet. The
structured run record (v0.2) is the shared substrate for all of this and ships
first.

**2026-06-30 — v1.0 tracked via a readiness epic; governance gated on public 1.0 (ci, #296).**
Defined 1.0 readiness as an epic (#296) tracking the remaining differentiation
work (#254 GitHub Actions integration, #261 `uio serve`) plus governance (#295),
rather than collapsing everything into the `v1.0` milestone. This applies the
project's two-axis model: an issue keeps its release milestone (*when*, e.g. #254
in v0.3) while the epic captures the *initiative*. Governance hardening (#295 —
DCO, REUSE/SPDX, public RFC) is gated on **before public 1.0** and assigned to the
`v1.0` milestone; it stays `backlog` until the 1.0 cut. Backlog priority is
tracked with the board's `Order` field (no calendar dates pre-1.0, since timing is
fluid).

**2026-06-30 — Make PM config declarative; retire M1–M7 for release milestones (ci, #286).**
Closed the gap left by the initial PM adoption: issue types, milestones, and the
Project board's custom fields are now declared in `.github/project.yml` and
reconciled by a deterministic `project-sync` workflow + script (mirroring
`labels-sync`), rather than documented as manual UI steps. Board *views* and
*auto-add* stay manual (no GitHub API) and are tracked as `backlog`. The M1–M7
phase milestones (the completed GitHub-App-identity initiative) were retired to
`closed` in favour of release-themed milestones (`v0.2`–`v1.0`). Org-level
reconciliation uses a maintainer `PROJECT_ADMIN_TOKEN`, deliberately outside the
least-privilege agent identities.

**2026-06-29 — Adopt GitHub-native PM taxonomy & component labeling (ci, #286).**
Reviewed the fighters-legacy PM framework and adopted its lightest, highest-value
lessons: path-based `component:*` PR labels mirroring conventional-commit scopes,
an Epic/Feature/Task/Spike/Bug issue-type taxonomy (Feature reuses the existing
`enhancement` label), a triage checklist, and this dated decision-log format.
Deferred DCO/REUSE-SPDX/public-RFC governance as friction uio does not yet need.

**2025-XX-XX — Python as the implementation language (core).** uio is I/O-bound
(LLM calls, subprocess orchestration) and string/parsing-heavy, so a systems
language offered no real speedup while costing iteration velocity and ecosystem
fit. See [Why Python?](#why-python) above. (Back-dated example entry.)
