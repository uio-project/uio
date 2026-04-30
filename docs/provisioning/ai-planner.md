# Provisioning Guide — AI Planner GitHub App

> **M2a deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Provision the `uio-ai-planner` GitHub App with minimum permissions for issue and PR planning.
>
> **Prerequisite:** Permission matrix must be approved (#57) before provisioning.

---

## Overview

The AI Planner identity handles issue creation, issue comments, and PR comments on behalf
of uio planning agents. It has **no code write access** — it cannot push commits, create
branches, or merge pull requests.

| Identity | `github-identity` value | Primary operations |
|---|---|---|
| AI Planner | `planner` | Issue create/edit · Issue comments · PR comments |

---

## Step 1 — Create the GitHub App

Navigate to your GitHub account settings and create the app:

1. Go to **[github.com/settings/apps/new](https://github.com/settings/apps/new)**
   (for a personal account) or **Settings → Developer settings → GitHub Apps → New GitHub App**
   under an organisation.

2. Fill in the registration form:

   | Field | Value |
   |---|---|
   | **GitHub App name** | `uio-ai-planner` |
   | **Homepage URL** | `https://github.com/jomkz/uio` |
   | **Webhook — Active** | **Uncheck** (no webhooks needed) |

3. Under **Repository permissions**, set:

   | Permission | Access |
   |---|---|
   | Issues | **Read and write** |
   | Pull requests | **Read and write** |
   | Metadata | **Read-only** (mandatory) |
   | Contents | **No access** |

   All other permissions must remain **No access**.

4. Under **Where can this GitHub App be installed?**, select:
   **Only on this account** (restricts installation to `jomkz`).

5. Click **Create GitHub App**.

6. Note the **App ID** shown on the app settings page — you will need it shortly.

---

## Step 2 — Generate the private key

On the app settings page, scroll to **Private keys** and click
**Generate a private key**. GitHub downloads a `.pem` file named
`uio-ai-planner.YYYY-MM-DD.private-key.pem`.

Store it securely (see §4 below). **Never commit this file to a repository.**

---

## Step 3 — Install the app in pilot repositories

1. On the app settings page, click **Install App** in the left sidebar.
2. Click **Install** next to the `jomkz` account.
3. Under **Repository access**, select **Only select repositories** and add:
   - `jomkz/uio`

   Do **not** select "All repositories" — least-privilege requires explicit repo scope.

4. Click **Install**.

5. After installation, note the **Installation ID** from the URL:
   `https://github.com/settings/installations/<INSTALLATION_ID>`.

---

## Step 4 — Store credentials securely

Add the three required environment variables to your local secrets file.
The `~/.config/uio/secrets` convention matches the pattern used by other
uio credential configuration:

```bash
# ~/.config/uio/secrets  (chmod 600, sourced by ~/.bashrc or ~/.zshrc)

export GITHUB_APP_PLANNER_ID="<app_id_from_step_1>"
export GITHUB_APP_PLANNER_INSTALLATION_ID="<installation_id_from_step_3>"
export GITHUB_APP_PLANNER_PRIVATE_KEY="$HOME/.config/uio/uio-ai-planner.private-key.pem"
```

Move the downloaded `.pem` file to the path above:

```bash
mkdir -p ~/.config/uio
mv ~/Downloads/uio-ai-planner.*.private-key.pem ~/.config/uio/uio-ai-planner.private-key.pem
chmod 600 ~/.config/uio/uio-ai-planner.private-key.pem
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
python scripts/validate_github_identity.py planner jomkz/uio
```

Expected output (abridged):

```
[planner] Authenticating...
[planner] Token obtained — expires 2026-05-01T12:00:00Z
[planner] Permissions granted by installation:
    issues: write       ✓ (required: write)
    pull_requests: write  ✓ (required: write)
    metadata: read      ✓ (required: read)
[planner] Forbidden permissions (must be absent):
    contents:           ✓ absent
[planner] Connectivity check — GET /rate_limit: 200 OK
✅ AI Planner identity validated successfully.
```

If any permission is unexpected, revisit Step 1 and adjust the app's
repository permission settings, then re-install the app.

---

## Acceptance criteria checklist

- [ ] App named `uio-ai-planner` created under the `jomkz` account
- [ ] Repository permissions: Issues R/W · PRs R/W · Metadata R · Contents: None
- [ ] App installed in `jomkz/uio` only (not "all repositories")
- [ ] Private key stored at `~/.config/uio/uio-ai-planner.private-key.pem` (chmod 600)
- [ ] Env vars set: `GITHUB_APP_PLANNER_ID`, `GITHUB_APP_PLANNER_INSTALLATION_ID`, `GITHUB_APP_PLANNER_PRIVATE_KEY`
- [ ] `python scripts/validate_github_identity.py planner jomkz/uio` passes

---

*See `docs/provisioning/ai-coder.md` and `docs/provisioning/ai-reviewer.md` for M2b and M2c.*
*See `docs/github-permission-matrix.md` (M1b, #57) for the approved permission matrix.*
