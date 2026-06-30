# Runbook — GitHub App Audit

> **M5c deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Covers logging requirements and audit review for actions taken by the three uio GitHub
> App identities (AI Planner, AI Coder, AI Reviewer).

---

## What uio logs

The uio runner emits a structured log line whenever it authenticates as a GitHub App
identity. Log output goes to `stderr` and is captured by whatever process invokes
`uio agent run`.

### Log fields

| Field | Example | Description |
|---|---|---|
| `identity` | `planner` | The `github-identity` value from the agent frontmatter |
| `app_name` | `uio-ai-planner` | Display name of the GitHub App |
| `agent` | `github-planner` | Agent definition filename (without extension) |
| `action` | `token_exchange` | Type of authentication event |
| `repo` | `uio-project/uio` | Repository the token was scoped to (from `GITHUB_APP_*_INSTALLATION_ID`) |
| `token_expires` | `2026-05-01T12:34:00Z` | ISO-8601 expiry of the installation token |
| `timestamp` | `2026-05-01T12:24:00Z` | UTC time of the event |

### Capturing logs

Redirect `stderr` to a log file when running agents in production:

```bash
uio agent run github-planner "Create issue in uio-project/uio ..." 2>>~/.local/share/uio/audit.log
```

Or capture both streams with timestamps using `ts` (from `moreutils`):

```bash
uio agent run github-coder "..." 2>&1 | ts '[%Y-%m-%dT%H:%M:%S]' >>~/.local/share/uio/audit.log
```

---

## GitHub audit log review

GitHub records all API actions taken by an App installation in the organisation or
account audit log. For a personal account (`jomkz`), use the GitHub web UI or API.

### Web UI review

1. Go to **github.com → Settings → Security log** (personal account) or
   **github.com/organisations/<org> → Settings → Audit log** (organisation).
2. Filter by actor: type `actor:app/uio-ai-planner` (or `uio-ai-coder`, `uio-ai-reviewer`).
3. Set a date range covering the last 90 days.
4. Review the event list. Expected event types:
   - `issues.create`, `issues.comment` — AI Planner
   - `pull_request.create`, `git.push` — AI Coder
   - `pull_request.comment` — AI Reviewer
5. Flag any event type not in the expected list and open an incident issue (see
   `docs/runbooks/github-app-incident-response.md`).

### API review

```bash
# Fetch the last 100 audit events for the AI Planner app
gh api "/users/jomkz/events" --jq '.[] | select(.actor.login | startswith("uio-ai-"))' | head -50

# Fetch repo-level events for a specific app
gh api "repos/uio-project/uio/events" \
  --jq '.[] | select(.actor.login | startswith("uio-ai-")) | {type, created_at, actor: .actor.login, repo: .repo.name}'
```

---

## Quarterly audit checklist

Run this during each quarterly governance review (see `docs/governance.md`):

- [ ] Review the last 90 days of GitHub audit log for each of the three app identities.
- [ ] Confirm no event types outside the expected set occurred.
- [ ] Confirm no action was taken against a repository outside the approved installation scope.
- [ ] Review the local `audit.log` (if captured) for token exchange frequency anomalies.
- [ ] Confirm all tokens expired normally (no manual revocation events).
- [ ] If anomalies are found, open an incident issue immediately (see
      `docs/runbooks/github-app-incident-response.md`).

---

*See `docs/runbooks/github-app-incident-response.md` for incident escalation steps.*
*See `docs/governance.md` for the quarterly review process.*
