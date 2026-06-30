# Runbook — Branch Protection Baseline

> **M5b deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Documents the branch protection configuration applied to pilot repositories to ensure
> AI Coder-generated PRs cannot bypass human review.

---

## Protection baseline (applied 2026-04-30)

The following protection is applied to the `main` branch of `uio-project/uio`.
Reproduce it with the command in §Reconfiguration below.

| Control | Setting |
|---|---|
| Require pull request | **Yes** — no direct push to `main` |
| Required approving reviews | **0** — PR required but no external approval (sole maintainer; human IS the reviewer for AI Coder PRs) |
| Dismiss stale reviews | **Yes** — new commits invalidate prior approvals |
| Require code owner review | No (no CODEOWNERS file) |
| Require status checks | **Yes** — all four CI jobs must pass |
| Require branches to be up to date | **Yes** (`strict: true`) |
| Force push | **Blocked** |
| Branch deletion | **Blocked** |

### Required status checks

| Check | Workflow |
|---|---|
| `Test (Python 3.11)` | `.github/workflows/ci.yml` — test matrix |
| `Test (Python 3.12)` | `.github/workflows/ci.yml` — test matrix |
| `Test (Python 3.13)` | `.github/workflows/ci.yml` — test matrix |
| `Lint` | `.github/workflows/ci.yml` — ruff lint |

---

## AI Coder bypass verification

The AI Coder GitHub App (`uio-ai-coder`) has **no branch protection bypass permission**.
Verify at any time with:

```bash
gh api repos/uio-project/uio/branches/main/protection/restrictions 2>&1
# Expected: {"message":"Push restrictions not enabled", ...}
# A 404 with "Push restrictions not enabled" confirms no bypass list exists.
```

Additionally confirm in the GitHub UI:
1. Go to `uio-project/uio` → Settings → Branches → Edit protection rule for `main`.
2. Under "Allow specified actors to bypass required pull requests", confirm the
   `uio-ai-coder` app is **not** listed.

---

## CODEOWNERS assessment

`uio-project/uio` does not currently have a `CODEOWNERS` file. The current protection
(PR required, CI must pass) is sufficient for the M6 pilot as a sole-maintainer
project. Consider adding `CODEOWNERS` if the project gains additional maintainers and
path-specific ownership becomes necessary.

To add CODEOWNERS later:
1. Create `.github/CODEOWNERS` with ownership rules.
2. Update the branch protection rule: set `require_code_owner_reviews: true`.

---

## Reconfiguration

If branch protection is accidentally removed or needs to be reproduced after a repo
migration, apply it with:

```bash
gh api repos/uio-project/uio/branches/main/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      {"context": "Test (Python 3.11)"},
      {"context": "Test (Python 3.12)"},
      {"context": "Test (Python 3.13)"},
      {"context": "Lint"}
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false
}
EOF
```

After reconfiguring, run the bypass verification check above.

---

## Extending to additional repositories

When installing AI Coder in a new repository (see [installation policy in
`docs/governance.md`](../governance.md#installation-policy)), apply an equivalent
baseline to that repository's default branch before enabling the agent.

Minimum required controls for any new pilot repo:

- Require PR before merge (no direct push)
- Dismiss stale reviews on new commits
- Require passing CI status checks (adapt check names to that repo's workflow)
- Block force push and branch deletion

For multi-maintainer repositories, set `required_approving_review_count: 1` to enforce
human review on AI Coder PRs via branch protection rather than trusting agent constraints
alone.

---

*See `docs/governance.md` for the installation approval policy.*
*See `docs/github-permission-matrix.md` for the AI Coder permission set.*
