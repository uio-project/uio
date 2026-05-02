---
name: quality-checks
description: Detect the project's code quality toolchain and run it against the entire project.
---

# Skill: quality-checks

## Input

- `project-path` — root directory of the project to check (required)

## Output

Code is formatted and linted. Any errors that could not be auto-fixed are reported and the skill stops without committing.

## Steps

### 1. Detect the toolchain

Inspect the project files at `project-path` to determine which tools to run:

| File present | Tools to run |
|---|---|
| `pyproject.toml` with `[tool.ruff]` | `ruff format .` then `ruff check --fix .` |
| `pyproject.toml` with `[tool.black]` | `black .` then `flake8` |
| `.pre-commit-config.yaml` | `pre-commit run --all-files` |
| `Makefile` with a `lint` or `format` target | `make lint` / `make format` |

Use the first match in the order above. If none match, skip this skill and note that no quality toolchain was detected.

### 2. Run against the entire project

Always run against the **entire project** (`.`), not just changed files. This matches what CI does and catches pre-existing issues on the branch that would otherwise block the PR.

```bash
cd <project-path>
# example for ruff:
ruff format .
ruff check --fix .
```

### 3. Report results

- If all tools exit 0: report "quality checks passed" and continue.
- If any tool exits non-zero after auto-fixing: print the full tool output and stop. Do not commit.
