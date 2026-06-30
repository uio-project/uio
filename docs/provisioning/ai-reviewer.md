# Provisioning Guide — AI Reviewer GitHub App

> **M2c deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Provision the `uio-ai-reviewer` GitHub App with minimum permissions for pull request
> diff reading and review comment posting.
>
> **Prerequisite:** Permission matrix must be approved (#57) before provisioning.

---

## Overview

The AI Reviewer identity reads pull request diffs and posts structured review comments on
behalf of uio review agents. It has **no merge or approval authority** — it cannot approve
or merge pull requests, and it cannot push code.

| Identity | `github-identity` value | Primary operations |
|---|---|---|
| AI Reviewer | `reviewer` | PR diff read · Structured review comments |

---

## Step 1 — Create the GitHub App

Navigate to your GitHub account settings and create the app:

1. Go to **[github.com/settings/apps/new](https://github.com/settings/apps/new)**
   (for a personal account) or **Settings → Developer settings → GitHub Apps → New GitHub App**
   under an organisation.

2. Fill in the registration form:

   | Field | Value |
   |---|---|
   | **GitHub App name** | `uio-ai-reviewer` |
   | **Homepage URL** | `https://github.com/uio-project/uio` |
   | **Webhook — Active** | **Uncheck** (no webhooks needed) |

3. Under **Repository permissions**, set:

   | Permission | Access |
   |---|---|
   | Pull requests | **Read and write** |
   | Issues | **Read and write** |
   | Metadata | **Read-only** (mandatory) |
   | Contents | **Read-only** |
   | Checks | **Read-only** |

   All other permissions must remain **No access**.

4. Under **Where can this GitHub App be installed?**, select:
   **Only on this account** (restricts installation to `jomkz`).

5. Click **Create GitHub App**.

6. Note the **App ID** shown on the app settings page — you will need it shortly.

---

## Step 2 — Generate the private key

On the app settings page, scroll to **Private keys** and click
**Generate a private key**. GitHub downloads a `.pem` file named
`uio-ai-reviewer.YYYY-MM-DD.private-key.pem`.

Store it securely (see §4 below). **Never commit this file to a repository.**

---

## Step 3 — Install the app in pilot repositories

1. On the app settings page, click **Install App** in the left sidebar.
2. Click **Install** next to the `jomkz` account.
3. Under **Repository access**, select **Only select repositories** and add:
   - `uio-project/uio`

   Do **not** select "All repositories" — least-privilege requires explicit repo scope.

4. Click **Install**.

5. After installation, note the **Installation ID** from the URL:
   `https://github.com/settings/installations/<INSTALLATION_ID>`.

---

## Step 4 — Store credentials securely

Add the three required environment variables to your local secrets file:

```bash
# ~/.config/uio/secrets  (chmod 600, sourced by ~/.bashrc or ~/.zshrc)

export GITHUB_APP_REVIEWER_ID="<app_id_from_step_1>"
export GITHUB_APP_REVIEWER_INSTALLATION_ID="<installation_id_from_step_3>"
export GITHUB_APP_REVIEWER_PRIVATE_KEY="$HOME/.config/uio/uio-ai-reviewer.private-key.pem"
```

Move the downloaded `.pem` file to the path above:

```bash
mkdir -p ~/.config/uio
mv ~/Downloads/uio-ai-reviewer.*.private-key.pem ~/.config/uio/uio-ai-reviewer.private-key.pem
chmod 600 ~/.config/uio/uio-ai-reviewer.private-key.pem
```

Source the secrets file (or open a new terminal):

```bash
source ~/.config/uio/secrets
```

---

## Step 5 — Validate

Run the uio identity validation script to confirm authentication works and
the permission set matches the approved matrix:

```bash
python scripts/validate_github_identity.py reviewer uio-project/uio
```

Expected output (abridged):

```
[reviewer] Authenticating...
[reviewer] Token obtained — expires 2026-05-01T12:00:00Z
[reviewer] Permissions granted by installation:
    pull_requests: write  ✓ (required: write)
    issues: write         ✓ (required: write)
    metadata: read        ✓ (required: read)
    contents: read        ✓ (required: read)
    checks: read          ✓ (required: read)
[reviewer] Forbidden permissions (must be absent):
    administration:       ✓ absent
[reviewer] Connectivity check — GET /rate_limit: 200 OK
✅ AI Reviewer identity validated successfully.
```

If any permission is unexpected, revisit Step 1 and adjust the app's
repository permission settings, then re-install the app.

---

## Acceptance criteria checklist

- [ ] App named `uio-ai-reviewer` created under the `jomkz` account
- [ ] Repository permissions: PRs R/W · Issues R/W · Metadata R · Contents R · Checks R
- [ ] App installed in `uio-project/uio` only (not "all repositories")
- [ ] Private key stored at `~/.config/uio/uio-ai-reviewer.private-key.pem` (chmod 600)
- [ ] Env vars set: `GITHUB_APP_REVIEWER_ID`, `GITHUB_APP_REVIEWER_INSTALLATION_ID`, `GITHUB_APP_REVIEWER_PRIVATE_KEY`
- [ ] `python scripts/validate_github_identity.py reviewer uio-project/uio` passes

---

*See `docs/provisioning/ai-planner.md` and `docs/provisioning/ai-coder.md` for M2a and M2b.*
*See `docs/github-permission-matrix.md` (M1b, #57) for the approved permission matrix.*
