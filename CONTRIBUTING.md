# Contributing to uio

Thank you for your interest in contributing! This document covers everything you need to get started.

## Table of contents

- [Code of Conduct](#code-of-conduct)
- [Getting started](#getting-started)
- [Development workflow](#development-workflow)
- [Running tests](#running-tests)
- [Code style](#code-style)
- [Commit messages](#commit-messages)
- [Pull requests](#pull-requests)
- [Reporting bugs](#reporting-bugs)
- [Requesting features](#requesting-features)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to abide by its terms.

## Getting started

```bash
# Fork and clone the repo
git clone https://github.com/<your-username>/uio.git
cd uio

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Development workflow

1. Create a branch from `main`:
   ```bash
   git checkout -b feat/short-description   # new feature
   git checkout -b fix/short-description    # bug fix
   ```

2. Make your changes, write tests, update docs as needed.

3. Verify everything passes (see below).

4. Push and open a pull request against `main`.

## Running tests

```bash
# Run the full test suite
pytest

# With coverage
pytest --cov=uio --cov-report=term-missing
```

All tests must pass before a PR can be merged.

## Code style

uio uses [ruff](https://docs.astral.sh/ruff/) for formatting and linting.

```bash
# Format
ruff format .

# Lint (auto-fix safe issues)
ruff check --fix .
```

The CI pipeline enforces both checks on every PR. You can add a pre-commit hook to catch issues locally:

```bash
pip install pre-commit
pre-commit install
```

## Commit messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) spec:

```
<type>(<scope>): <short summary>

<optional body>
```

Common types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`.

Examples:
```
feat(cli): add --timeout flag to agent run
fix(registry): handle missing manifest gracefully
docs: update quickstart for v0.2
```

## Pull requests

- Keep PRs focused — one logical change per PR.
- Fill in the PR template (it loads automatically).
- Reference the issue your PR closes: `Closes #N`.
- All CI checks must pass.
- At least one maintainer approval is required before merge.

## Reporting bugs

Use the [Bug Report](https://github.com/uio-project/uio/issues/new?template=bug_report.yml) issue template. Include:
- `uio --version` and `python --version` output
- Minimal reproduction steps
- The full error / traceback

## Requesting features

Use the [Feature Request](https://github.com/uio-project/uio/issues/new?template=feature_request.yml) issue template. Describe the problem, your proposed solution, and any alternatives you considered.
