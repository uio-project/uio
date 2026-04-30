# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Completed M6a controlled end-to-end pilot with the github-planner, github-coder, and github-reviewer GitHub App identities.

### Added

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

[Unreleased]: https://github.com/jomkz/uio/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jomkz/uio/releases/tag/v0.1.0
