---
name: github-clone-repo
description: Clone a GitHub repository to a local path and check out a branch.
---

# Skill: github-clone-repo

## Input

- `owner/repo` — repository to clone (required)
- `target-path` — local filesystem path to clone into (required). Callers should use an
  isolated path derived from both the repo and the branch (e.g. `/tmp/<repo>-<branch-slug>`,
  where `<branch-slug>` is the branch name with `/` replaced by `-`) so that concurrent or
  sequential runs on the same repo do not share state.
- `branch` — branch to check out after cloning (optional; defaults to the repository's default branch)

## Output

The repository is cloned at `target-path`, checked out on `branch`, and up to date with origin.

## Steps

```bash
gh repo clone <owner>/<repo> <target-path> --depth 1
git -C <target-path> checkout <branch>
git -C <target-path> pull origin <branch>
```

If `branch` is not provided, omit the `checkout` step — the default branch is already active after cloning.

If the `target-path` already exists (e.g. a previous run left it behind), skip the clone and run only the `pull` step:

```bash
git -C <target-path> fetch origin
git -C <target-path> checkout <branch>
git -C <target-path> pull origin <branch>
```

If `git pull` fails due to a diverged history, reset to the remote state:

```bash
git -C <target-path> reset --hard origin/<branch>
```

Stop and report an error if the clone or checkout fails for any reason other than the path already existing.
