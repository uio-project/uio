# GitHub Identity Inventory — Current State

> **M1a deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Establishes the baseline before splitting responsibilities across dedicated GitHub App identities.

---

## 1. Agent and skill definitions — GitHub action inventory

The table below covers all bundled definitions (shipped via `uio init --examples`)
plus the structural categories of community registry definitions.

### Bundled definitions

| Definition | File | Action type | Auth required | Repo scope |
|---|---|---|---|---|
| repo-health | `repo-health.agent.md` | PR list (read) | Yes — `gh pr list` via MCP | Working directory repo |
| repo-health | `repo-health.agent.md` | Branch list (read) | No — `git branch` local | Working directory repo |
| repo-health | `repo-health.agent.md` | Commit history (read) | No — `git log` local | Working directory repo |
| shell-helper | `shell-helper.agent.md` | None — generic shell | N/A | N/A |
| summarise | `summarise.skill.md` | None — text processing | N/A | N/A |
| explain-code | `explain-code.skill.md` | None — `cat` read | N/A | N/A |
| changelog-entry | `changelog-entry.skill.md` | `git diff` (local, no auth) | No | Working directory repo |
| debug-traceback | `debug-traceback.skill.md` | None — text processing | N/A | N/A |
| ask-docs | `ask-docs.prompt.md` | None by default; user-driven | Conditional | User-defined |

**Finding:** Only `repo-health` performs a GitHub API operation (`gh pr list`). It is
read-only and does not create or modify any resource.

### GitHub App identity mapping (target state)

When community agents are built under epic #53, each new agent will declare a role:

| Planned agent | GitHub-identity | Actions | Repo scope |
|---|---|---|---|
| `github-planner.agent.md` | `planner` | Issue CRUD, triage (type + `component:*` labels), PR comments, issue comments | User-configured |
| `github-coder.agent.md` | `coder` | Branch create, file push, PR create | User-configured |
| `github-reviewer.agent.md` | `reviewer` | PR review, PR comment, diff summary | User-configured |
| `closer.agent.md` | `closer` | Verify criteria, close issues, append decision-log entries | User-configured |

---

## 2. Credential entry points

### Environment variables consumed by uio

| Variable | Read in | Purpose | PAT or App token? |
|---|---|---|---|
| `GITHUB_PERSONAL_ACCESS_TOKEN` | `uio/core/mcp.py:101` | Start GitHub MCP server; token forwarded to MCP process env | **PAT (personal)** |
| `GITHUB_TOKEN` | `uio/core/mcp.py:101` | Fallback if `GITHUB_PERSONAL_ACCESS_TOKEN` absent | PAT or GITHUB_ACTIONS token |
| `GITHUB_TOKEN` | `uio/registry/manifest.py:48` | Authorization header for private registry manifest/file fetches | PAT or GITHUB_ACTIONS token |
| `GH_TOKEN` | `gh` CLI (subprocess) | `gh` CLI uses this when set; overrides any `~/.config/gh/hosts.yml` auth | Set by runner post #61 |
| `GITHUB_APP_<ROLE>_ID` | `uio/core/github_app.py` | GitHub App ID for the named role | App credential |
| `GITHUB_APP_<ROLE>_INSTALLATION_ID` | `uio/core/github_app.py` | Installation ID for the named role | App credential |
| `GITHUB_APP_<ROLE>_PRIVATE_KEY` | `uio/core/github_app.py` | PEM key (literal or file path) for the named role | App credential |
| `MCP_GITHUB_COMMAND` | `uio/core/mcp.py:106` | Override MCP server launch command | N/A — command only |

### Docker Compose passthrough

Both the `uio` (CPU) and `uio-gpu` services in `docker-compose.yml` forward:

```yaml
- GITHUB_PERSONAL_ACCESS_TOKEN=${GITHUB_PERSONAL_ACCESS_TOKEN:-}
```

This makes the host's PAT available inside the container. After migration, these
entries must be replaced with App credential env vars per role.

### CI/CD usage

The `release.yml` workflow uses `secrets.GITHUB_TOKEN` (GitHub Actions built-in)
only for Docker registry login — **not for agent actions**. No agent definitions
are invoked in CI at present.

---

## 3. Code locations — where credentials are read or set

| File | Line(s) | Description |
|---|---|---|
| `uio/core/mcp.py` | 101–105 | Reads `GITHUB_PERSONAL_ACCESS_TOKEN` / `GITHUB_TOKEN`; passes to MCP server subprocess env |
| `uio/core/mcp.py` | 106 | Reads `MCP_GITHUB_COMMAND` to override MCP server launch |
| `uio/registry/manifest.py` | 47–49 | Reads `GITHUB_TOKEN` for private registry HTTP auth headers |
| `uio/core/runner.py` | `_maybe_inject_github_identity` | Sets `GH_TOKEN` from GitHub App installation token (added in #61) |
| `uio/core/github_app.py` | `from_env()` | Reads `GITHUB_APP_<ROLE>_{ID,INSTALLATION_ID,PRIVATE_KEY}` |
| `docker-compose.yml` | 31, 53 | Forwards `GITHUB_PERSONAL_ACCESS_TOKEN` from host env to container |

---

## 4. Repositories currently touched by uio-driven automation

uio itself has no hardcoded repository targets. All GitHub operations run in the
context of the directory where `uio` is invoked. The table below reflects the
repositories where uio has been used as part of this epic's own development.

| Repo | Operations performed | Identity used |
|---|---|---|
| `uio-project/uio` | Issue creation, issue comments, PR creation | Personal account (`jomkz`) via `gh` CLI |
| `uio-project/uio-registry` | Manifest fetches (read-only) | `GITHUB_TOKEN` (public repo — unauthenticated also works) |

**Finding:** All write operations today (issue creation, PR comments) are performed
by a personal account. There is no service account, bot, or GitHub App in use yet.

---

## 5. Personal-account dependencies to eliminate

The following items represent personal-credential dependencies that the enterprise
identity migration (epic #53) must remove:

| # | Dependency | Impact | Migration path |
|---|---|---|---|
| 1 | `GITHUB_PERSONAL_ACCESS_TOKEN` used for MCP server | All GitHub MCP operations run as a personal user | Per-identity App token set as `GH_TOKEN` before MCP startup; MCP server reads `GITHUB_PERSONAL_ACCESS_TOKEN` from env — override via `GH_TOKEN` already works for `gh` CLI, but MCP server needs explicit update in `mcp.py` |
| 2 | `GITHUB_PERSONAL_ACCESS_TOKEN` forwarded by Docker Compose | Container runs all agent operations as a personal user | Replace with `GITHUB_APP_PLANNER_*` / `GITHUB_APP_CODER_*` / `GITHUB_APP_REVIEWER_*` env vars |
| 3 | `gh` CLI uses personal OAuth session (`~/.config/gh/hosts.yml`) when `GH_TOKEN` is not set | Fallback path uses personal account | Ensure `GH_TOKEN` is always set by the runner when a GitHub identity is declared (done in #61) |
| 4 | Issue creation and PR comments in `uio-project/uio` performed by personal account | AI-generated issues are indistinguishable from human issues | After App provisioning (M2), re-run agent workflows with App identity set |

---

## 6. Summary — findings for M1b (permission matrix)

| Finding | Implication for M1b (#57) |
|---|---|
| Only one bundled agent touches GitHub (`repo-health` — read-only PR list) | Low migration risk for bundled agents; focus is on new registry agents |
| Credential is read in two independent places: MCP startup and registry fetches | MCP and registry should have independent credential scoping post-migration |
| No personal PATs are hardcoded in source code | No secret rotation is immediately required |
| All write operations are via personal account | Priority is AI Planner (issue/comment writes) as the first identity to provision |
| Docker Compose is the only deployment surface that passess credentials into the container | Migration is a single-file change in `docker-compose.yml` |

---

*This document was produced as part of M1a (#56). See #57 for the permission matrix.*
