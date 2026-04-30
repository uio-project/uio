# Runbook — GitHub App Incident Response

> **M5c deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Steps for responding to credential compromise or app misuse for the three uio GitHub
> App identities (AI Planner, AI Coder, AI Reviewer).

---

## Incident severity tiers

| Tier | Trigger | Target response |
|---|---|---|
| **P1 — Critical** | Private key confirmed stolen or exposed; malicious actions observed in audit log | Immediate (within 1 hour) |
| **P2 — High** | Suspicious audit log events; unexpected permission use; app installed in unintended repo | Same day (within 4 hours) |
| **P3 — Low** | Credential file exposed locally but not exfiltrated; misconfigured permissions detected | Next business day |

---

## P1 — Immediate response (compromise confirmed)

Execute these steps in order. Do not skip ahead.

### Step 1 — Suspend the app installation immediately

```bash
# Suspend installation — replaces all tokens and blocks new ones
gh api installations/<INSTALLATION_ID>/suspended --method PUT
```

Replace `<INSTALLATION_ID>` with the value from `GITHUB_APP_*_INSTALLATION_ID`:

```bash
# Planner
gh api installations/$GITHUB_APP_PLANNER_INSTALLATION_ID/suspended --method PUT

# Coder
gh api installations/$GITHUB_APP_CODER_INSTALLATION_ID/suspended --method PUT

# Reviewer
gh api installations/$GITHUB_APP_REVIEWER_INSTALLATION_ID/suspended --method PUT
```

### Step 2 — Revoke the private key

1. Go to **github.com/settings/apps/uio-ai-planner** (or coder / reviewer).
2. Under **Private keys**, click **Delete** next to the compromised key.
3. Confirm deletion. All JWTs signed with this key become immediately invalid.

### Step 3 — Open an incident issue

```bash
gh issue create --repo jomkz/uio \
  --label "ai-governance,security,incident" \
  --title "INCIDENT [P1]: GitHub App credential compromise — <identity>" \
  --body "## Incident report

**Identity affected:** <planner | coder | reviewer>
**Detected:** $(date -u '+%Y-%m-%dT%H:%M:%SZ')
**Detected by:** <name>
**Initial indicators:** <describe what was observed>

## Actions taken
- [ ] App installation suspended (Step 1)
- [ ] Private key revoked (Step 2)
- [ ] Audit log review in progress (Step 4)
- [ ] New key generated and deployed (Step 5)

## Audit findings
_Fill in after Step 4_"
```

### Step 4 — Review audit log for blast radius

```bash
# Review all actions by the compromised identity in the last 30 days
gh api "repos/jomkz/uio/events" \
  --jq '.[] | select(.actor.login | startswith("uio-ai-")) | {type, created_at, actor: .actor.login}'
```

Document any unauthorised actions (unexpected repos, unexpected event types, unexpected
volume) in the incident issue. If code was pushed by AI Coder to unexpected locations,
review those commits immediately.

### Step 5 — Generate a new private key and redeploy

1. Go to the app settings page.
2. Under **Private keys**, click **Generate a private key**.
3. Download and store the new key:

```bash
mv ~/Downloads/uio-ai-<role>.*.private-key.pem ~/.config/uio/uio-ai-<role>.private-key.pem
chmod 600 ~/.config/uio/uio-ai-<role>.private-key.pem
```

4. Update the `GITHUB_APP_<ROLE>_PRIVATE_KEY` env var if the filename changed.
5. Source the secrets file: `source ~/.config/uio/secrets`

### Step 6 — Unsuspend the installation

```bash
gh api installations/$GITHUB_APP_<ROLE>_INSTALLATION_ID/suspended --method DELETE
```

### Step 7 — Validate

```bash
python scripts/validate_github_identity.py <role> jomkz/uio
```

Confirm the output shows `✅` before returning to normal operations.

### Step 8 — Post-incident review

Within 5 business days of the incident, post a post-mortem to the incident issue
covering: timeline, root cause, corrective actions, and any governance rule changes.
Close the issue after the post-mortem is complete.

---

## P2 — Suspicious activity (unconfirmed compromise)

1. Do **not** suspend the installation yet — investigate first to avoid false-positive
   disruption.
2. Open a P2 incident issue using the template above (change label to `incident`).
3. Review the audit log (see `docs/runbooks/github-app-audit.md`).
4. If suspicious activity is confirmed, escalate to P1 immediately.
5. If activity is explained (misconfiguration, test run), document the explanation and
   close the issue.

---

## P3 — Local exposure (no exfiltration)

1. Rotate the private key (see `docs/runbooks/github-app-credential-rotation.md`).
2. Document the incident in the quarterly review issue.
3. Review local filesystem access controls: `ls -la ~/.config/uio/`.

---

*See `docs/runbooks/github-app-credential-rotation.md` for credential rotation steps.*
*See `docs/runbooks/github-app-emergency-disable.md` for the fast-path disable procedure.*
*See `docs/runbooks/github-app-audit.md` for audit log review steps.*
