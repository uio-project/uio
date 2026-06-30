# Runbook — GitHub App Emergency Disable

> **M5c deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Fast-path procedure for immediately revoking a uio GitHub App installation when
> suspicious activity is detected or a security incident is declared.

---

## When to use this runbook

Use this runbook when you need to **stop all GitHub API activity from an App identity
immediately** and cannot wait to investigate first. Examples:

- Audit log shows unexpected repository access or unexpected event types
- A private key file has been confirmed exfiltrated
- An agent is running amok (creating many issues/PRs/commits unexpectedly)
- A security researcher reports a vulnerability in the GitHub App identity chain

For confirmed P1/P2 incidents requiring a full post-mortem, continue into
`docs/runbooks/github-app-incident-response.md` after completing this runbook.

---

## Fast-path disable (< 2 minutes)

### Option A — Suspend the installation (recommended)

Suspending an installation revokes all currently-valid tokens and prevents new tokens
from being issued, without deleting the App or its configuration. This is reversible.

```bash
# Suspend AI Planner
gh api installations/$GITHUB_APP_PLANNER_INSTALLATION_ID/suspended --method PUT

# Suspend AI Coder
gh api installations/$GITHUB_APP_CODER_INSTALLATION_ID/suspended --method PUT

# Suspend AI Reviewer
gh api installations/$GITHUB_APP_REVIEWER_INSTALLATION_ID/suspended --method PUT
```

Verify suspension:

```bash
gh api installations/$GITHUB_APP_PLANNER_INSTALLATION_ID \
  --jq '{suspended_at, suspended_by: .suspended_by.login}'
```

Expected: `suspended_at` is a recent timestamp.

Any currently running `uio agent run` process will fail on its next API call (within
seconds to minutes, depending on cached token TTL). Kill the process if needed:

```bash
pkill -f "uio agent run"
```

### Option B — Delete the private key (irreversible until new key generated)

If you cannot access the installation ID env vars (e.g., secrets file is inaccessible),
delete the private key directly from the GitHub UI:

1. Go to `github.com/settings/apps/uio-ai-planner` (or coder / reviewer).
2. Under **Private keys**, click **Delete** next to the active key.
3. Confirm deletion.

Any JWT signed with the deleted key will be rejected immediately, and no new JWTs can
be issued until a new key is generated.

### Option C — Uninstall the app from the repository

If you only need to stop the app from acting on a specific repository (not all repos):

```bash
# List installations to find the installation ID for the specific repo
gh api app/installations --jq '.[] | {id, account: .account.login}'

# Delete the installation for that repo
gh api installations/<INSTALLATION_ID> --method DELETE
```

**Warning:** This permanently removes the installation. The app must be reinstalled
(including approval per the installation policy) to restore access.

---

## After the emergency disable

1. **Open an incident issue immediately:**

   ```bash
   gh issue create --repo uio-project/uio \
     --label "ai-governance,incident" \
     --title "Emergency disable: <identity> — <date>" \
     --body "**Disabled at:** $(date -u '+%Y-%m-%dT%H:%M:%SZ')
   **Reason:** <brief description>
   **Method used:** Option A / B / C (see runbook)
   **Follow-up:** See docs/runbooks/github-app-incident-response.md"
   ```

2. **Do not re-enable** until the incident issue has been investigated and a root cause
   documented (see `docs/runbooks/github-app-incident-response.md`).

3. **To re-enable** after investigation is complete:

   ```bash
   # Unsuspend (reverses Option A)
   gh api installations/$GITHUB_APP_<ROLE>_INSTALLATION_ID/suspended --method DELETE

   # Validate
   python scripts/validate_github_identity.py <role> uio-project/uio
   ```

---

## Quick reference — installation IDs

Your installation IDs are stored in `~/.config/uio/secrets`:

```bash
grep INSTALLATION_ID ~/.config/uio/secrets
```

If the secrets file is unavailable, retrieve installation IDs from GitHub:

```bash
gh api /app/installations --jq '.[] | {id, account: .account.login, app_id}'
```

Note: this requires the App's JWT, which requires the private key. If the private key
is also unavailable, use **Option C** (delete via GitHub UI) instead.

---

## Testing this runbook (non-production apps only)

Before the M6 pilot launch, test the emergency disable procedure against a non-production
copy of one of the apps:

1. Create a test GitHub App with identical permissions.
2. Run `uio agent run github-planner "..."` in the background.
3. Execute Option A (suspend) and confirm the running process fails within 5 minutes.
4. Unsuspend and validate.
5. Document the test result in the M6 pilot issue.

---

*See `docs/runbooks/github-app-incident-response.md` for the full P1/P2 incident process.*
*See `docs/runbooks/github-app-credential-rotation.md` for key rotation after re-enable.*
*See `docs/governance.md` for the escalation path and quarterly review process.*
