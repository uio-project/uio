---
name: setup-python-env
description: Detect the project's Python package manager and bootstrap a virtual environment with all dependencies installed.
---

# Skill: setup-python-env

## Input

- `project-path` — root directory of the Python project (required)
- `python-version` — preferred Python version (e.g. `3.12`); defaults to the version declared in `pyproject.toml`, `.python-version`, or `runtime.txt`, falling back to the system default (optional)

## Output

A virtual environment exists at `<project-path>/.venv`, is activated for the remainder of the workflow, and all project dependencies (including dev extras) are installed.

## Steps

### 1. Detect the package manager

Inspect the files at `project-path` and use the **first** match in this priority order:

| Condition | Tool | Bootstrap commands |
|---|---|---|
| `uv.lock` present **or** `[tool.uv]` in `pyproject.toml` | `uv` | `uv venv .venv && uv pip install -e ".[dev]"` |
| `poetry.lock` present | `poetry` | `poetry install` |
| `Pipfile.lock` present | `pipenv` | `pipenv install --dev` |
| `requirements-dev.txt` present | `pip` | `python -m pip install -r requirements-dev.txt` |
| `requirements.txt` present | `pip` | `python -m pip install -r requirements.txt` |
| `pyproject.toml` present (no lock file) | `pip` | `python -m pip install -e ".[dev]"` |
| None of the above | — | Warn and skip; do not abort the parent workflow |

> **`pip` invocation**: always use `python -m pip` rather than bare `pip` to avoid `PATH` issues.

### 2. Bootstrap the environment

Run the detected bootstrap commands from `project-path`:

```bash
cd <project-path>
# example for pip + pyproject.toml:
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

For `uv`: if `.venv` already exists, skip `uv venv` and proceed directly to `uv pip install`.

For `poetry` and `pipenv`: these tools manage their own virtual environments; do not create `.venv` manually.

If the selected tool is not installed, try the next tool in the priority list rather than failing immediately.

If no tool succeeds, report a clear error listing what was tried and stop.

### 3. Verify the environment

Confirm the environment is active and dependencies are installed:

```bash
python -c "import sys; print(sys.executable)"
```

If this fails, report the error and stop.
