# About uio

## Origin

uio didn't start as a design. It started as duplication.

The immediate predecessor was a custom agent runner built inside another personal project — a multi-repo
workspace with a handful of automated AI workflows: a manager agent that triaged CI failures, a scanner
that audited code health, a finisher that opened pull requests, a release manager that gated environment
promotions. Each agent was a markdown file with YAML frontmatter. Each run was a tool-use loop: send a
system prompt to an LLM, receive a response, execute any tool calls, feed results back, repeat.

The runner itself was about 800 lines of Python across two files. It handled provider selection (Gemini,
OpenAI, Ollama), model routing by task complexity, MCP server integration for GitHub operations, a
cost ledger, and a Click CLI for local and CI invocation. It worked well. It also looked very familiar.

The pattern — definition files, a tool loop, provider abstraction, cost tracking — had appeared before
in experiments with other tools. The runner wasn't solving a problem specific to that project; it was
re-implementing a general capability that any project would eventually want. Maintaining it alongside
the project it served meant two things were always slightly out of sync: improvements to one didn't
automatically help the other.

---

## The extraction

The decision to extract wasn't taken lightly. Premature abstraction is its own kind of maintenance
burden. The test was: *could a second project drop this in and get the same result without modification?*

The answer was yes, provided a few things were true:

1. **The definition format had to be stable.** Frontmatter fields needed a clear schema — `name`,
   `description`, `complexity`, `capabilities` — with known semantics and validation.
2. **The CLI had to be generic.** `uio agent run manager` had to mean the same thing in any project,
   not just the one where the runner was born.
3. **Project-specific commands had to stay out.** Commands like `myapp env` or `myapp issue`
   belonged to the host project, not the runtime. The runtime's job was to execute definitions.
4. **Configuration had to be layered.** A `uio.toml` in the project root could override defaults
   without the caller needing to pass flags on every invocation.

The extraction happened incrementally. The core tool loop became `uio/core/runner.py`. The client
abstractions became `uio/core/clients.py`. The CLI grew subcommand groups for `agent`, `prompt`,
`skill`, `chat`, `cost`, and `config`. The definition files stayed exactly as they were — the format
that worked in the source project worked unchanged in the library.

---

## Why "uio"

The name carries two readings that reinforce each other.

The first is borrowed from the Linux kernel's **UIO** subsystem — Userspace I/O. In Linux, UIO lets
device driver logic live in userspace rather than inside the kernel. The kernel module exposes a
minimal interface; the real behaviour is implemented in a plain userspace process. This dramatically
lowers the barrier to writing drivers: no kernel module build, no kernel memory management, no risk
of a bug crashing the whole system. The kernel provides the plumbing; you provide the logic.

uio applies the same idea to AI agents. The runtime provides the plumbing — the tool loop, provider
routing, MCP integration, cost ledger. The agent logic lives in a plain markdown file. You don't
need to write a custom runner, wire up an LLM client, or build a CLI. The framework exposes a minimal
interface; the real behaviour is in the definition files.

The second reading — **Universal Input/Output** — describes what the runtime does at a practical level.
Input: definition files. Any project, any provider, any LLM. You write a markdown file; that's the
input interface. Output: LLM responses, tool execution results, cost ledger entries. Whatever the
agent produces flows back out. The runtime is the universal channel between the two.

What makes this more than a coincidence is that both readings map to the same underlying structure.
In Linux UIO, hardware events come in, control signals go out, and userspace logic sits in between —
the kernel is the universal channel. In uio, definition files come in, responses and actions go out,
and your markdown logic sits in between — the runtime is the universal channel. The analogy holds at
both levels: the design philosophy and the runtime behaviour describe the same thing from different
angles.

The analogy isn't perfect — nothing involving LLMs is as deterministic as a kernel interface — but
the design principle holds: **push logic to the edge, keep the core minimal and stable**.

One footnote on how the name was actually found: the only initial constraint given to an AI when
brainstorming was "three characters, easy to type." `uio` came back in the candidate list. The Linux
UIO connection was discovered afterwards — which made it an easy choice. Sometimes the right name
finds you.

---

## What it is now

uio is a lightweight, provider-agnostic framework for defining and running AI agents, skills, and
prompts. Definitions live as markdown files with YAML frontmatter. The `uio` CLI discovers and
executes them against any supported LLM provider.

The framework deliberately avoids opinions about *what your agents do*. It has opinions about *how
definitions are structured* (the frontmatter schema), *how providers are selected* (the routing
chain), and *how costs are tracked* (the ledger format). Everything else — the system prompt, the
tool-use strategy, the stopping condition — is yours.

That scope came directly from the extraction: the runner that existed before was already scoped that
way. Nothing was added to make it "a framework." The abstraction boundary was already there; uio
just made it explicit and standalone.
