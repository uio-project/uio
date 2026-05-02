---
name: project-context
description: High-level context about this project injected into every agent run.
scope: project
---

This repository is **uio** — a provider-agnostic AI agent/skill/prompt runner.

Key facts agents should know:
- Definition files live under `.uio/agents/`, `.uio/skills/`, `.uio/prompts/`, and `.uio/memory/`.
- The primary CLI entry point is `uio`. Run `uio --help` to see all subcommands.
- CI runs `ruff format --check .` and `ruff check .` for linting, and `pytest -m "not integration"` for tests.
- GitHub operations use the `gh` CLI or MCP GitHub tools; prefer MCP when available.
