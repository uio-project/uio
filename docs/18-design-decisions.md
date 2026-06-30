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
