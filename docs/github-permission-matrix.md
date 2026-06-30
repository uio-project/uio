# GitHub App Permission Matrix & Separation of Duties

> **M1b deliverable** for epic #53 (Enterprise GitHub Identity Architecture for AI Agents).
> Defines minimum permissions, explicit exclusions, and the uio agent→identity routing map.
> Builds on the current-state inventory in `docs/github-identity-inventory.md` (M1a, #56).

---

## 1. Permission matrix — identity × GitHub permission × repo scope

The three GitHub App identities map to distinct responsibility domains. Permissions follow
the GitHub Apps API permission model (resource: access level).

### AI Planner (`planner`)

**Purpose:** Create and comment on issues and PRs. No code write access.

| Permission | Level | Rationale |
|---|---|---|
| Issues | Read/Write | Create issues, post issue comments |
| Pull requests | Read/Write | Post PR comments, read PR metadata |
| Metadata | Read | Required by GitHub for all Apps |
| Contents | **None** | Planner does not read or write code |
| Checks | **None** | Not required for planning work |

**Initial repo installation scope:** `uio-project/uio` only.

---

### AI Coder (`coder`)

**Purpose:** Create branches, commit code, open PRs. No issue management.

| Permission | Level | Rationale |
|---|---|---|
| Contents | Read/Write | Push commits, create branches |
| Pull requests | Read/Write | Open PRs, update PR descriptions |
| Metadata | Read | Required by GitHub for all Apps |
| Issues | Read | Read issues for context; write only if needed post-pilot review |
| Checks | Read | Observe CI status |

**Initial repo installation scope:** `uio-project/uio` only.

---

### AI Reviewer (`reviewer`)

**Purpose:** Review PRs, post inline comments, summarise diffs. No code write access.

| Permission | Level | Rationale |
|---|---|---|
| Pull requests | Read/Write | Submit reviews, post PR comments |
| Issues | Read/Write | Post issue comments when a review surfaces a defect |
| Metadata | Read | Required by GitHub for all Apps |
| Contents | Read | Read code for diff analysis |
| Checks | Read | Observe CI status during review |

**Initial repo installation scope:** `uio-project/uio` only.

---

## 2. Explicit capability exclusions (all three identities)

The following capabilities are permanently excluded from all three App identities unless
explicitly re-evaluated and approved via the escalation path defined in §5.

| Capability | Excluded from | Reason |
|---|---|---|
| Merge pull requests | All | Human review gate must not be bypassable by AI |
| Approve pull requests | Planner, Coder | Approval is a human trust signal |
| Push to `main` directly | All | Branch protection enforces PR-only writes |
| Write workflow files (`.github/workflows/`) | All | CI/CD modification is out of scope for the pilot |
| Organisation admin access | All | Never required for agent tasks |
| Repository admin access | All | Never required for agent tasks |
| Manage GitHub Actions secrets | All | Secrets are a human responsibility |
| Delete branches or repositories | All | Destructive; no agent use case |

---

## 3. Separation of duties — what each identity owns

The matrix below clarifies ownership boundaries. "Owner" means the identity has write
access and is the primary actor. "Consumer" means read access for context only.

| Action | Planner | Coder | Reviewer |
|---|---|---|---|
| Create/edit issues | **Owner** | Consumer | Consumer |
| Comment on issues | **Owner** | — | Owner |
| Create branches | — | **Owner** | — |
| Commit and push code | — | **Owner** | — |
| Open pull requests | — | **Owner** | — |
| Post PR review comments | — | — | **Owner** |
| Approve pull requests | — | — | _Humans only_ |
| Merge pull requests | _Humans only_ | _Humans only_ | _Humans only_ |

**Cross-boundary rule:** An identity must not perform an action in a column that is not
its own "Owner" or "Consumer" cell. Violations should be treated as a misconfiguration.

---

## 4. uio agent → identity routing map

This table maps all current and planned uio definitions to a `github-identity` value
(the frontmatter field introduced in M3a, #61). Definitions with no GitHub operations
carry no identity.

### Bundled definitions (shipping in `uio init --examples`)

| Definition file | GitHub actions | `github-identity` | Notes |
|---|---|---|---|
| `repo-health.agent.md` | `gh pr list` (read) | _(none — no write ops)_ | Read-only; personal `GH_TOKEN` or anonymous is sufficient |
| `shell-helper.agent.md` | None | _(none)_ | Generic shell; no GitHub operations |
| `summarise.skill.md` | None | _(none)_ | Text processing only |
| `explain-code.skill.md` | None | _(none)_ | Local `cat` read only |
| `changelog-entry.skill.md` | `git diff` (local) | _(none)_ | No remote GitHub operations |
| `debug-traceback.skill.md` | None | _(none)_ | Text processing only |
| `ask-docs.prompt.md` | Conditional/user-driven | _(none — user-configured)_ | User controls auth |

**Finding:** No bundled definition requires a GitHub App identity. The `github-identity`
field is reserved for registry agents with explicit write operations.

---

### Planned registry definitions (M4, #64–#67)

| Definition file | GitHub actions | `github-identity` | Prohibited cross-boundary actions |
|---|---|---|---|
| `github-planner.agent.md` | Issue create/edit, PR/issue comments | `planner` | Cannot push code, cannot create branches |
| `github-coder.agent.md` | Branch create, commit, push, PR create | `coder` | Cannot create issues as primary actor, cannot approve PRs |
| `github-reviewer.agent.md` | PR review, PR inline comments, diff summary | `reviewer` | Cannot push code, cannot open PRs as author |

---

## 5. Human review requirements for AI Coder PRs

All pull requests opened by the AI Coder identity must satisfy the following before merge:

1. **Branch protection rule** — the target branch (`main` and `develop`) requires at least
   one human approving review. AI Reviewer approval alone does not satisfy this requirement.
2. **Required status checks** — all CI checks must pass before merge is enabled.
3. **Draft PR until ready** — AI Coder should open PRs as drafts and convert to ready-for-review
   only after all self-checks pass, reducing premature human notification.
4. **Attribution disclosure** — PR body must include the disclosure footer (M3c, #63):
   `🤖 Generated with [uio](https://github.com/uio-project/uio)`.

---

## 6. Escalation path for higher-risk permissions

If a future use case requires a capability currently excluded in §2, the following steps apply:

1. **Proposal** — open an issue tagged `ai-governance` describing the use case, the specific
   permission required, and the risk model.
2. **Review** — at minimum one human reviewer (project maintainer) must approve the proposal issue.
3. **Trial scope** — any new permission is initially granted to a single non-production repository
   for a defined trial period (≥2 weeks).
4. **Post-trial review** — document observed behaviour and any anomalies before widening scope.
5. **Quarterly review** — all App permissions are reviewed quarterly against the principle of
   least privilege; unused permissions are revoked.

---

## 7. Summary — findings for M2 (GitHub App provisioning)

| Identity | App name (suggested) | Permissions to configure | Install repos |
|---|---|---|---|
| `planner` | `uio-ai-planner` | Issues: R/W · PRs: R/W · Metadata: R | `uio-project/uio` |
| `coder` | `uio-ai-coder` | Contents: R/W · PRs: R/W · Metadata: R · Issues: R · Checks: R | `uio-project/uio` |
| `reviewer` | `uio-ai-reviewer` | PRs: R/W · Issues: R/W · Metadata: R · Contents: R · Checks: R | `uio-project/uio` |

*This document was produced as part of M1b (#57). See #58–#60 for GitHub App provisioning.*

---

## Acceptance criteria checklist

- [x] Each GitHub App identity has a clearly defined purpose and minimum permission set (§1)
- [x] High-risk capabilities are explicitly excluded with rationale (§2)
- [x] Separation of duties is documented with clear ownership boundaries (§3)
- [x] The uio routing map covers all bundled and planned definitions (§4)
- [x] Human review requirements for AI Coder PRs are specified (§5)
- [x] Escalation path for future higher-risk permissions is defined (§6)
