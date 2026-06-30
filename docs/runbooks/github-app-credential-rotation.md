# Runbook — GitHub App Credential Rotation

> **M5c deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Procedure for rotating the private key of a uio GitHub App identity without service
> interruption.

---

## When to rotate

| Trigger | Timeline |
|---|---|
| Routine annual rotation | Within 30 days of the 12-month anniversary of the last rotation |
| Quarterly review finding (key > 12 months old) | Within 2 weeks of the review |
| P3 incident (local exposure, no confirmed exfiltration) | Within 24 hours |
| P1/P2 incident | Immediately — follow `docs/runbooks/github-app-incident-response.md` instead |

---

## How GitHub App key rotation works

GitHub Apps support **multiple private keys simultaneously**. This means:

1. Generate and upload the new key — both old and new keys are valid.
2. Deploy the new key to all machines using it.
3. Delete the old key — only the new key is valid.

There is **no downtime** if you follow this order. Never delete the old key before
deploying the new one.

---

## Rotation procedure

### Step 1 — Generate a new private key (keep the old one active)

1. Go to the app settings page:
   - AI Planner: `github.com/settings/apps/uio-ai-planner`
   - AI Coder: `github.com/settings/apps/uio-ai-coder`
   - AI Reviewer: `github.com/settings/apps/uio-ai-reviewer`

2. Under **Private keys**, click **Generate a private key**.
   GitHub downloads `uio-ai-<role>.YYYY-MM-DD.private-key.pem`.

   At this point, **both the old key and the new key are valid**. The old key continues
   to work — no agent runs will be interrupted.

### Step 2 — Store and permission the new key

```bash
# Move to the standard location (use a temp name first)
mv ~/Downloads/uio-ai-<role>.*.private-key.pem \
   ~/.config/uio/uio-ai-<role>.private-key.new.pem
chmod 600 ~/.config/uio/uio-ai-<role>.private-key.new.pem
```

### Step 3 — Validate the new key before activating it

```bash
# Temporarily point the env var at the new key
GITHUB_APP_<ROLE>_PRIVATE_KEY=~/.config/uio/uio-ai-<role>.private-key.new.pem \
  python scripts/validate_github_identity.py <role> uio-project/uio
```

If validation fails (token exchange error, permission mismatch), stop here. Do not
rename or delete the old key. Investigate the failure and retry from Step 1.

### Step 4 — Activate the new key

```bash
# Replace the active key file atomically
mv ~/.config/uio/uio-ai-<role>.private-key.new.pem \
   ~/.config/uio/uio-ai-<role>.private-key.pem
```

The `GITHUB_APP_<ROLE>_PRIVATE_KEY` env var already points to this path — no env
change is needed. Source the secrets file to pick up any env changes:

```bash
source ~/.config/uio/secrets
```

### Step 5 — Validate with the active key

```bash
python scripts/validate_github_identity.py <role> uio-project/uio
```

Confirm output shows `✅` before proceeding.

### Step 6 — Delete the old key from GitHub

1. Return to the app settings page.
2. Under **Private keys**, identify the old key by its fingerprint or creation date.
3. Click **Delete** next to the old key.
4. Confirm deletion.

The old key is now invalid. Any cached JWTs signed with it will be rejected after their
9-minute TTL expires naturally.

### Step 7 — Record the rotation

Update the **Last key rotation** field in the app documentation record in
`docs/governance.md` by opening a PR:

```
**Last key rotation:** YYYY-MM-DD
```

Post a comment on the quarterly review issue (or open one if outside the review cycle)
noting the rotation date and reason.

---

## Multi-machine deployment

If the private key is used on more than one machine (e.g., a CI runner and a developer
workstation):

1. Complete Steps 1–3 on **all machines** before executing Step 4 on any of them.
2. Execute Steps 4–5 on all machines.
3. Then execute Step 6 (delete old key) only after all machines have validated Step 5.

---

## Verifying key age

Check the key creation date from the GitHub UI or via the API:

```bash
gh api /app/installations --jq '.[0].app_id'
# Then visit: github.com/settings/apps/<app-name> → Private keys
```

The key creation date is shown next to each key's fingerprint. Keys older than 12 months
should be flagged in the quarterly review.

---

*See `docs/runbooks/github-app-incident-response.md` for emergency rotation (P1/P2).*
*See `docs/runbooks/github-app-emergency-disable.md` for fast-path disable.*
*See `docs/governance.md` for the quarterly review process.*
