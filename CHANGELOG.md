# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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
