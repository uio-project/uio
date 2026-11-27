# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Read-only agents on current Claude models (#359):
  - **Built-in file tools.** `read_file`, `list_files` and `search_files` only read, and stay
    inside the run's working directory: a path out of it, through `..` or a symbolic link, is
    refused.
  - **`builtin-tools:`.** This new frontmatter key chooses which built-in tools an agent is
    offered. Without it the agent gets `run_command`, as before. An agent offered only the file
    tools is neither given a shell nor told about one, and a call to a built-in tool it was not
    offered runs nothing. `tools:`, which some editors use in these files, is still ignored.
  - **`guardrails.final_turn`.** At the turn cap the model is asked once more, with every tool
    off, so a run that hits its limit answers from what it found instead of ending with nothing.
  - **A gateway in front of Anthropic.** `--base-url`, `ANTHROPIC_BASE_URL` and a bearer token
    (`ANTHROPIC_AUTH_TOKEN`, which alone makes the provider available) all reach the Anthropic
    provider.
  - **Prompt caching.** Every Anthropic call caches the system prompt, the tool list and the
    newest message, so each turn of a loop reads its history from the cache. The ledger records
    `cache_read_tokens` and `cache_write_tokens`, and the cost estimate prices them at a tenth
    of the input rate and at 1.25 times it.
- Roadmap restructure toward a fleet-capable 1.0 (#296): six release milestones
  (`v0.3` refocused as *Editor, CI & Evals*, `v0.4` as *Trust & Observability*,
  new `v0.5 — Serve & Events` and `v0.6 — Fleet`), a narrative roadmap
  (`docs/21-roadmap.md`), and the serve→fleet architecture decision — stateless
  `uio serve` workers on a pluggable durable queue (SQLite → Postgres
  `SKIP LOCKED`), a GitOps fleet manifest, transactional cost leases, and
  eval-gated canary rollout of definitions. New epics cover supply-chain trust,
  run-record observability, definition evals as CI artifacts, adaptive runtime,
  agent interop (MCP hosting, A2A), serve, and fleet. Adds
  `component:serve`/`component:fleet`/`component:eval` labels and a pytest guard
  for the declarative PM config (`tests/test_project_config.py`).
- GitHub-native project-management framework (#286): path-based `component:*` PR
  labeling, a versioned label set with sync workflow, Task/Epic/Spike issue
  templates, a label & issue-type taxonomy, an issue triage checklist, a dated
  decision-log format, and a project-setup runbook. Planner and closer agents
  now apply issue types/labels and append decision-log entries.
- Declarative project-management state (#286): `.github/project.yml` is the source
  of truth for org issue types, milestones, and the Project board's custom fields,
  reconciled by the `project-sync` workflow + `scripts/project-sync.sh`. Retired
  the M1–M7 phase milestones in favour of release-themed milestones (`v0.2`–`v1.0`).
- `.pre-commit-config.yaml` mirroring the CI ruff checks plus a conventional-commit
  hook (resolves the gap referenced by `CONTRIBUTING.md`).

### Changed

- Anthropic on Claude 5 (#359): the tier defaults are `claude-sonnet-5-5` (large) and
  `claude-haiku-5-5` (small). The cost table adds Fable 5.2, Opus 5.5, Sonnet 5.5 and Haiku 5.5.

### Fixed

- Extended thinking on current Claude models (#359): a `complexity: large` run sent a fixed
  `budget_tokens`, which Claude 4.7 and later refuse with a 400. Claude 4.6 and later now get
  adaptive thinking; older models keep the budget.


## [0.2.0] - 2026-06-29

### Changed

- Migrated all repository references from the `jomkz/uio` org to `uio-project/uio`.
- Completed M6a controlled end-to-end pilot with the github-planner, github-coder, and github-reviewer GitHub App identities.

### Added

- `closer` agent for verifying acceptance criteria and closing parent issues/epics
- Code coverage reporting in CI
- CI workflow: pytest across Python 3.11–3.13, ruff lint/format checks
- Release workflow: build wheel + sdist, publish to PyPI via Trusted Publisher, create GitHub Release
- Issue templates: bug report and feature request (structured forms)
- Pull request template with checklist
- Dependabot: weekly pip and GitHub Actions dependency updates
- `CONTRIBUTING.md`: setup, workflow, style, commit, and PR guidelines
- `CHANGELOG.md`: this file

## [0.1.0] - 2025-01-01

### Added

- Initial release: provider-agnostic agent/skill/prompt runner
- CLI (`uio`) with `agent run`, `skill run`, `prompt run`, `chat`, `cost`, `init`, `registry` sub-commands
- Bundled examples and remote registry discovery
- Full documentation suite in `docs/`

[Unreleased]: https://github.com/uio-project/uio/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/uio-project/uio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/uio-project/uio/releases/tag/v0.1.0
