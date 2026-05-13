# Where uio Sits

> uio occupies a distinct niche: **definition-as-code automation**. The agents,
> skills, and prompts you author live in your repo, run headlessly in CI/CD, carry
> distinct GitHub App identities, and produce auditable cost records. Other tools in
> this space are chat/session-first and interactive — they are what you open when you
> want to build something at a terminal. uio is what runs at 3am when no one is watching.

---

## The niche: headless, definition-driven automation

Interactive AI assistants (chat UIs, IDE plugins, terminal REPLs) are optimised for a
human-in-the-loop workflow: you type, the model responds, you iterate. That is a
perfectly valid way to work, and uio does not try to compete with it.

uio is designed for the other moment: the push hook, the scheduled pipeline, the
overnight batch job. No human present. No interactive session. Just a definition file
checked into git, an LLM invocation, and an auditable output committed back to the
repo.

That distinction drives almost every design decision in uio — from the YAML frontmatter
schema to the [JSONL cost ledger](10-cost.md) to the
[GitHub App identity system](17-github-app-identities.md).

---

## Comparison table

| Dimension | Interactive tools | uio |
|---|---|---|
| Primary mode | Interactive TUI / chat | Headless / scriptable |
| Definition model | None (chat-driven) | Markdown files, version-controlled |
| CI/CD fit | Underdeveloped / absent | Core use case |
| Cost tracking | None | JSONL ledger, `uio cost` |
| Multi-agent GitHub identities | No | planner / coder / reviewer App identities |
| Definition sharing | No | Git-hosted [registries](11-registry.md) |
| Complexity routing | No | small / large tiers with extended thinking |
| Iteration caps | No | Per-tier caps, configurable |

---

## What this means in practice

When you author a uio agent you are writing a versioned, reviewable, reusable
automation artefact — not a session transcript. It lives next to your source code,
evolves with it through pull requests, and runs the same way in your laptop CI and in
production.

The [use cases page](15-use-cases.md) shows end-to-end examples: repo health
monitoring, automated code review, issue planning, AI-authored pull requests, and
multi-agent pipelines with distinct GitHub identities.

The [GitHub App identities page](17-github-app-identities.md) covers how uio gives
each agent role (planner, coder, reviewer) a separate GitHub App identity so that
automated commits and comments are attributable, auditable, and permission-scoped.

The [cost ledger page](10-cost.md) covers the JSONL ledger format and the `uio cost`
command — every token spent by every agent run is recorded and queryable.

The [registry page](11-registry.md) covers how definition files can be shared and
installed from git-hosted registries, so automation patterns are reusable across teams
and organisations.

---

## The risk: invisibility

uio is not competing for the same user at the same moment as interactive tools. The
risk is not displacement — it is invisibility: the CI/CD automation niche is real, but
uio needs to be louder about owning it.

If you are evaluating uio and asking "how does this compare to the tool I already have
open in my terminal?" — that is the wrong comparison. The right question is: "what
runs my agents at 3am, commits the output to a PR, and tells me what it cost?"
