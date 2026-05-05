# Design decisions

This page documents the rationale behind key design decisions in uio.

---

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

**Summary:** Python is well-matched to what uio actually does. uio's value is in its agent
definitions and workflow logic — the language that lets you iterate fastest on prompts, routing,
and integrations is the right one.
