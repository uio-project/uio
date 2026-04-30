# Use Cases

> Worked examples of uio in practice — from single-agent runs to multi-identity pipelines.
> Each section shows a real pattern with the commands you'd actually run.

---

## 1. Repository health monitoring

**Agent:** `repo-health` (bundled example)  
**Pattern:** on-demand or scheduled single-agent run

`repo-health` produces a structured report covering failing tests, lint issues, open TODOs,
stale branches, and PR backlog. Run it before a release or wire it into CI to surface
regressions before they reach production.

```bash
# On-demand run against the current repo
uio agent run repo-health

# Pin a specific provider and model
uio agent run repo-health --provider gemini --model gemini-2.5-flash

# Run in CI (GitHub Actions)
- name: Repository health check
  run: uio agent run repo-health
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    GITHUB_PERSONAL_ACCESS_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

The agent reads the local filesystem, runs `git`, and calls `gh` to check open PRs and
issues. No configuration beyond an API key and a GitHub token is required.

---

## 2. Automated code review

**Agent:** `github-reviewer` (uio-registry)  
**Pattern:** event-driven, triggered when a PR opens

`github-reviewer` reads the full PR diff, checks context files, and posts a structured
review with a severity table (🔴 High / 🟡 Medium / 🟢 Low). It uses the `AI Reviewer`
GitHub App identity — its comments appear under a non-human account, making AI vs. human
authorship immediately visible.

```bash
# Install from registry
uio registry install github-reviewer

# Review a specific PR
uio agent run github-reviewer "jomkz/uio#42"

# Or with a full URL
uio agent run github-reviewer "https://github.com/jomkz/uio/pull/42"
```

Prerequisites: `GITHUB_APP_REVIEWER_*` env vars set (see
[Provisioning — AI Reviewer](provisioning/ai-reviewer.md)).

The agent never approves or merges — it posts a comment and stops. Human sign-off is
always required before merge.

---

## 3. Issue triage and planning

**Agent:** `github-planner` (uio-registry)  
**Pattern:** multi-step planning loop

`github-planner` turns natural-language descriptions into structured GitHub issues with
context, goal, and acceptance criteria sections. It can also decompose a large feature
into child issues. This is how the GitHub identity architecture (epic #53) in this very
repo was planned:

```bash
# Install from registry
uio registry install github-planner

# Create a single issue
uio agent run github-planner \
  "Create an issue in jomkz/uio titled 'Add rate limiting to the API' \
   describing exponential backoff with a 10 req/s default"

# Decompose a feature into child issues
uio agent run github-planner \
  "Break down the feature 'Enterprise GitHub Identity Architecture' \
   into implementable child issues in jomkz/uio"

# Comment on an existing issue with a triage assessment
uio agent run github-planner "jomkz/uio#53"
```

The planner has no code write access — it creates and comments on issues only.

---

## 4. AI-authored pull requests

**Agent:** `github-coder` (uio-registry)  
**Pattern:** code-change pipeline with mandatory human review gate

`github-coder` takes a natural-language change description, clones the repo, applies the
minimal change, commits with a non-human author identity, and opens a PR with an
AI-disclosure footer. The human review gate is enforced by branch protection — the PR
cannot be merged without a human approval.

```bash
# Install from registry
uio registry install github-coder

# Apply a change and open a PR
uio agent run github-coder \
  "Add input validation to the login endpoint | repo: jomkz/uio | branch: ai-coder/login-validation"

# With an explicit base branch
uio agent run github-coder \
  "Fix the off-by-one error in the token cache refresh | repo: jomkz/uio | base: develop"
```

Commits are authored as `uio AI Coder <uio-coder[bot]@users.noreply.github.com>`. The PR
body includes the AI disclosure footer automatically. The agent never merges — it stops
after opening the PR and reporting the URL.

Prerequisites: `GITHUB_APP_CODER_*` env vars set (see
[Provisioning — AI Coder](provisioning/ai-coder.md)).

---

## 5. Release notes generation

**Skill:** `changelog-entry` (bundled example)  
**Pattern:** invokable skill in a release workflow

Generate a conventional-commit changelog block from a git commit range, ready to paste
into `CHANGELOG.md` or a GitHub Release:

```bash
# Last 20 commits
uio skill run changelog-entry HEAD~20

# Between two tags
uio skill run changelog-entry v0.1.0..v0.2.0

# Or pipe directly into a file
uio skill run changelog-entry HEAD~10 >> CHANGELOG.md
```

Skills are single-shot — they produce output and exit without a tool-use loop, making
them fast and predictable for scripted workflows.

---

## 6. Multi-agent pipeline

**Pattern:** sequential plan → code → review with handoffs

The full value of GitHub App identities emerges when you chain agents: each identity acts
in its own lane, and human decisions gate each transition.

```bash
# 1. Plan — create the issue
uio agent run github-planner \
  "Create an issue in jomkz/uio for 'Add rate limiting to the MCP client'"
# → Creates issue #N

# 2. Code — implement the issue and open a PR
uio agent run github-coder \
  "Implement issue #N — add rate limiting to the MCP client | repo: jomkz/uio"
# → Opens PR #M with AI Coder identity

# 3. Review — post a structured review
uio agent run github-reviewer "jomkz/uio#M"
# → Posts review comment with severity table using AI Reviewer identity

# 4. Human reviews the findings and approves
# → Merge is gated on human approval; no agent can merge
```

This demonstrates the separation-of-duties model from
[`docs/github-permission-matrix.md`](github-permission-matrix.md): Planner writes issues,
Coder writes code, Reviewer reads and comments — no identity can act outside its lane.

---

## 7. CI/CD integration

**Pattern:** uio as a container step in GitHub Actions

The `ghcr.io/jomkz/uio` image runs uio agents without a local install. Use it to run
health checks, generate reports, or trigger planning agents on a schedule.

```yaml
name: Weekly repo health

on:
  schedule:
    - cron: "0 9 * * 1"   # Every Monday at 09:00 UTC

jobs:
  health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run repo health check
        run: |
          docker run --rm \
            -e GEMINI_API_KEY=${{ secrets.GEMINI_API_KEY }} \
            -e GITHUB_PERSONAL_ACCESS_TOKEN=${{ secrets.GITHUB_TOKEN }} \
            -v ${{ github.workspace }}:/workspace \
            ghcr.io/jomkz/uio agent run repo-health
```

For identity agents in CI, pass the App credentials as repository secrets and mount the
private key file (see [Container image](14-container.md#github-authentication-in-containers)).

---

## 8. Bootstrapping a new project

**Pattern:** init + registry install + first run

The fastest path from zero to a working multi-agent pipeline:

```bash
# 1. Install uio
pip install uio-ai

# 2. Scaffold .uio/ with bundled examples
uio init --examples

# 3. Add the official registry to uio.toml
cat >> uio.toml <<'EOF'
[[registries]]
name    = "official"
url     = "https://github.com/jomkz/uio-registry"
ref     = "main"
enabled = true
EOF

# 4. Install the GitHub identity agents
uio registry install github-planner github-coder github-reviewer

# 5. Set credentials and run
source ~/.config/uio/secrets   # GITHUB_APP_* vars
uio agent run github-planner "scaffold the backlog for my new API project in owner/repo"
```

From here, add `github-identity` to your own agent definitions to give them dedicated
GitHub identities — see [Frontmatter schema](04-frontmatter.md#github-identity).

---

*See [`docs/README.md`](README.md) for the full documentation index and suggested reading paths.*
