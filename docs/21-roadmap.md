# Roadmap

> The road to 1.0: stability → quality tooling → hardening → serve → fleet.
> uio 1.0 is the **fleet-capable, governance-hardened** cut — "what runs, *and
> operates*, your agents at 3am."

This is the narrative companion to the
[org project board](https://github.com/orgs/uio-project/projects/1). The board
is authoritative for status and sequencing; this page explains the *why* and the
architecture behind the milestone themes. Decisions are logged in
[design decisions](18-design-decisions.md); the PM model (types, labels,
milestones, epics) is described in [project management](project-management.md).

## The two-axis model

- **Milestones** answer *when*: `v0.2` through `v1.0`, release-themed, no
  calendar dates pre-1.0.
- **Epics** answer *what initiative*: an epic spans milestones and tracks its
  children via sub-issues.

## Milestones

| Milestone | Theme |
|---|---|
| **v0.2 — Stability & DX** | Hardening and foundations: structured **run records**, published JSON Schemas, sandboxing spike, security policy, SBOM, community health files. |
| **v0.3 — Editor, CI & Evals** | The CI-native quality story: GitHub Action, VS Code extension, and the **definition eval framework** (`uio eval`, golden traces, semantic `uio diff`, judge gates). |
| **v0.4 — Trust & Observability** | Harden the single-process runtime before it becomes a server: sandboxed tool execution, Sigstore/SLSA, secrets indirection, OpenTelemetry export, `uio explain`, checkpoint/resume. |
| **v0.5 — Serve & Events** | The event-driven runtime: `uio serve` daemon (HTTP API, durable queue, worker pool), webhooks, cron, SSE run streaming, MCP *hosting*, A2A. |
| **v0.6 — Fleet** | Clustered operation: shared queue, node registry, placement, GitOps fleet manifest, transactional cost leases, **eval-gated canary rollout**, watchdog agents. |
| **v1.0** | The fleet-capable, governance-hardened cut (DCO, REUSE/SPDX, RFC process). |

## Three strategic bets

### 1. The run record is the substrate

The JSONL cost ledger records *what a run cost*; the **structured run record**
(v0.2) records *what happened* — every model call, tool call, routing decision,
retry, and guardrail hit, in a versioned schema. Everything downstream builds on
it: OpenTelemetry spans, the `uio explain` audit narrative, eval golden traces,
checkpoint/resume, and cross-node handoff. It ships first because it is the
foundation for the rest of the roadmap.

### 2. Definitions get the full SDLC (evals as CI artifacts)

Agent definitions already live in git; v0.3 gives them the missing half of the
software lifecycle:

- **`*.eval.md` eval suites** live beside the definitions they test and run in
  CI with real exit codes (assertions: structured-output schema,
  contains/regex, LLM-judge rubric, cost ceiling).
- **Golden trace replay** (`uio eval --replay`) re-asserts against recorded run
  records without live LLM calls — cheap, deterministic eval CI.
- **`uio diff`** produces an LLM-generated *behavioral* diff of a definition
  change, posted on the PR by the reviewer identity.
- The **adaptive runtime** learns from ledger history but expresses every
  adaptation **as a PR, never runtime mutation** — the audit-first property is
  non-negotiable.

### 3. The fleet is GitOps on a boring queue

The serve→fleet architecture, chosen over a Kubernetes operator (abandons the
pip/binary DX; duplicates in etcd what git already provides) and over
coordinator-free gossip (hard budget caps must be transactional, not eventually
consistent):

```
webhooks / cron / A2A                    fleet manifest repo (git)
        │                                 pinned definition versions,
        ▼                                 budgets, guardrails, placement
  ┌───────────┐    durable queue                    │ reconcile
  │ uio serve │──▶ SQLite (single node)     ┌───────▼───────┐
  │  (node)   │    Postgres SKIP LOCKED ◀───│ uio serve × N │
  └───────────┘    (multi-node)             └───────┬───────┘
        │                                           │
        ▼                                           ▼
  run records ──────────▶ fleet ledger (cost leases, append-only)
```

- **Stateless workers, pluggable queue.** `uio serve` (v0.5) runs against an
  embedded SQLite queue; v0.6 swaps in the Postgres `FOR UPDATE SKIP LOCKED`
  reference backend behind the same interface. No leader election — the
  database coordinates, git decides.
- **Git is the control plane.** A fleet-manifest repo declares which definition
  versions, budgets, guardrail overrides, and placement rules are live; nodes
  converge on it, reusing the registry machinery.
- **Cost leases.** A run must reserve its `max_cost_usd` against the shared
  ledger before starting, making fleet-wide budget caps transactional.
- **Headline: eval-gated canary rollout.** A definition change is a PR to the
  fleet manifest; canary nodes run its eval suite plus a shadow slice of live
  events; a judge + cost-regression gate promotes or auto-reverts — every step
  in one append-only fleet ledger. Deploy your agents like code.
- **The fleet operates itself.** The `fleet-watchdog` is a shipped uio
  definition: node health, stuck runs, and budget burn-rate are monitored by
  the same auditable machinery the fleet runs for its users.

## Epic map

| Epic | Initiative | Spans |
|---|---|---|
| Trustworthy by default | Supply chain (SBOM, Sigstore, SLSA), sandboxed tools, secrets | v0.2–v0.4 |
| Glass-box runtime | Run records, OpenTelemetry, explain, streaming | v0.2–v0.4 |
| Front door | Docs site, Homebrew, community health files | v0.2–v0.3 |
| Definition quality engineering | JSON Schemas, `uio eval`, golden traces, eval gate, `uio diff`, judge gates | v0.2–v0.5 |
| Adaptive runtime | Checkpoint/resume, routing tuner (as PRs), compaction, memory v2 | v0.4–v0.5 |
| Agent interop | `uio mcp serve` (host definitions as MCP tools), A2A endpoint | v0.5 |
| `uio serve` | Daemon, webhooks, cron, run API/SSE | v0.5 |
| `uio fleet` | Queue, registry, placement, manifest, leases, canary, watchdog | v0.6 |

## What 1.0 means

1.0 is deliberately *after* the fleet work: serve and fleet churn public
interfaces (run-record schema, queue API, frontmatter keys), and pre-1.0 is the
license to break them. The [1.0 readiness epic](https://github.com/uio-project/uio/issues/296)
gates the cut on: `uio serve` GA, the eval-gated canary headline, and
[governance hardening](https://github.com/uio-project/uio/issues/295)
(DCO, REUSE/SPDX, public RFC process).
