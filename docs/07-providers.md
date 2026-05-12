# Providers

uio supports three built-in providers and any OpenAI-compatible endpoint. This page explains how to configure each one.

---

## Auto-routing

When no `--provider` flag is given, uio tries providers in this order:

```
Ollama  →  OpenAI  →  Gemini  →  Anthropic
```

A provider is included in the chain if its required API key is present in the environment. Ollama has no key requirement and is always tried first (as long as the Ollama process is running). Paid providers follow in ascending cost order.

The first provider in the chain that initialises successfully is used. To see which provider would be selected for the current environment:

```bash
uio config show
```

To force a specific provider for a single run:

```bash
uio agent run my-agent --provider openai
```

To set a default provider for a project:

```toml
# uio.toml
[runtime]
default_provider = "gemini"
```

To set it in the environment for all projects:

```bash
export LLM_PROVIDER=gemini
```

---

## Gemini

**Key env var:** `GEMINI_API_KEY`

1. Go to [Google AI Studio](https://aistudio.google.com/apikey) and generate an API key.
2. Export it:
   ```bash
   export GEMINI_API_KEY=your-key-here
   ```

Gemini is the recommended starting point — the small tier (`gemini-2.5-flash-lite`) has very low per-token costs and a generous free tier.

### Models

| Tier | Model | Notes |
|---|---|---|
| `small` | `gemini-2.5-flash-lite` | Default; fastest and cheapest |
| `large` | `gemini-2.5-flash` | Better reasoning; use for complex multi-step agents |

---

## Anthropic

**Key env var:** `ANTHROPIC_API_KEY`

1. Create an API key at [console.anthropic.com](https://console.anthropic.com/settings/keys).
2. Export it:
   ```bash
   export ANTHROPIC_API_KEY=your-key-here
   ```

### Models

| Tier | Model | Notes |
|---|---|---|
| `small` | `claude-haiku-4-5-20251001` | Fast and cost-efficient |
| `large` | `claude-sonnet-4-6` | Default; strong reasoning for complex agents |

> **Note:** The LiteLLM proxy workaround for Claude (previously documented below) is no longer needed. Use `--provider anthropic` or set `ANTHROPIC_API_KEY` directly.

### Extended thinking

When `complexity: large` is set (in frontmatter or via `--complexity large`), uio automatically enables Anthropic's extended thinking. The model reasons internally before producing its response, which improves accuracy on multi-step tasks at the cost of additional tokens.

The thinking budget is derived automatically from `max_tokens` (see below) and cannot be set independently.

### max_tokens

Anthropic requires an explicit `max_tokens` value. The default is `16000`, which provides ~10 000 tokens of thinking budget and ~6 000 tokens of output for large-complexity runs.

Override project-wide in `uio.toml`:

```toml
[runtime]
anthropic_max_tokens = 32000
```

Override per-agent in frontmatter:

```yaml
---
name: my-agent
complexity: large
max_tokens: 8192
---
```

---

## OpenAI

**Key env var:** `OPENAI_API_KEY`

1. Create an API key at [platform.openai.com](https://platform.openai.com/api-keys).
2. Export it:
   ```bash
   export OPENAI_API_KEY=your-key-here
   ```

### Models

| Tier | Model |
|---|---|
| `small` | `gpt-4o-mini` |
| `large` | `gpt-4o` |

---

## Ollama

**No API key required.** Ollama runs models locally.

1. Install Ollama: see [ollama.com](https://ollama.com)
2. Pull the default model:
   ```bash
   ollama pull llama3.1:8b
   ```
3. Ensure the Ollama server is running:
   ```bash
   ollama serve
   ```

By default, uio connects to `http://localhost:11434/v1`. Override with:

```bash
export OLLAMA_BASE_URL=http://my-server:11434/v1
```

All Ollama runs are recorded in the cost ledger with `estimated_cost_usd: 0.0`.

### Models

| Tier | Model |
|---|---|
| `small` | `llama3.1:8b` |
| `large` | `llama3.1:8b` |

---

## GitLab

GitLab is not an LLM provider — it is a **VCS provider** for agent definitions that use `vcs-identity` or `capabilities: [vcs]`. When `vcs-provider: gitlab` is set in frontmatter, uio wires up the GitLab MCP server's tool aliases so agents can use the provider-neutral `vcs__*` names against a GitLab instance.

### MCP server

The GitLab MCP server is the official `@gitlab/mcp-server` npm package maintained by GitLab.

**Install globally:**

```bash
npm install -g @gitlab/mcp-server
```

Alternatively, run it without a global install using npx (recommended — no installation step required):

```bash
npx -y @gitlab/mcp-server stdio
```

### Required environment variable

| Variable | Description |
|---|---|
| `GITLAB_TOKEN` | A GitLab personal access token with `api` scope |

Generate a token at **GitLab → User Settings → Access Tokens**. Select the `api` scope. No other scopes are required for standard agent operations.

```bash
export GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
```

### Register in `uio.toml`

Add the GitLab plugin under `[[mcp.plugins]]`:

```toml
[[mcp.plugins]]
name     = "gitlab"
type     = "vcs"
command  = "npx -y @gitlab/mcp-server stdio"
env_keys = ["GITLAB_TOKEN"]
```

The `type = "vcs"` field tells uio this plugin provides VCS tools. The `env_keys` list specifies which environment variables must be present for the plugin to be activated — if `GITLAB_TOKEN` is absent, the plugin is skipped and uio logs a warning.

### How it differs from GitHub

| Aspect | GitHub | GitLab |
|---|---|---|
| Tool prefix | `mcp__github__*` | `mcp__gitlab__*` |
| Pull requests | Called "pull requests" | Called "merge requests" |
| `vcs__list_pull_requests` | `mcp__github__list_pull_requests` | `mcp__gitlab__list_merge_requests` |
| `vcs__create_pull_request` | `mcp__github__create_pull_request` | `mcp__gitlab__create_merge_request` |
| `vcs__add_issue_comment` | `mcp__github__add_issue_comment` | `mcp__gitlab__create_note` |
| `vcs__get_file_contents` | `mcp__github__get_file_contents` | `mcp__gitlab__get_file` |
| `vcs__search_code` | `mcp__github__search_code` | `mcp__gitlab__search` |
| `vcs__merge_pull_request` | `mcp__github__merge_pull_request` | **No equivalent** |
| `vcs__search_repositories` | `mcp__github__search_repositories` | **No equivalent** |

The two GitHub-only aliases (`vcs__merge_pull_request` and `vcs__search_repositories`) have no GitLab counterpart. Agents that call these tools will receive a tool-not-found error when running against a GitLab deployment. Design provider-agnostic agents to avoid these two operations, or guard them behind a provider check.

See [VCS tool aliases](04-frontmatter.md#vcs-tool-aliases) in the frontmatter reference for the full alias table.

---

## LiteLLM proxy

LiteLLM provides an OpenAI-compatible proxy for 100+ providers (Anthropic, Mistral, Groq, Bedrock, etc.). uio's OpenAI client works with any LiteLLM deployment.

1. Install and start LiteLLM:
   ```bash
   pip install litellm
   litellm --model anthropic/claude-sonnet-4-6
   # Listening on http://0.0.0.0:4000
   ```
2. Configure uio to use it:
   ```bash
   export OPENAI_BASE_URL=http://localhost:4000
   export OPENAI_API_KEY=any-string   # LiteLLM virtual key or "sk-1234"
   ```
3. Optionally pin the model:
   ```bash
   uio agent run my-agent --model claude-sonnet-4-6
   ```

When `--model` is set, it bypasses tier selection and is sent directly to the proxy. The model name must match what the proxy expects.

---

## Azure OpenAI

1. Deploy a model in the Azure portal and note:
   - The endpoint URL: `https://my-resource.openai.azure.com/`
   - The deployment name: e.g. `gpt-4o-production`
   - The API key
2. Configure uio:
   ```bash
   export OPENAI_BASE_URL=https://my-resource.openai.azure.com/openai/deployments/gpt-4o-production
   export OPENAI_API_KEY=your-azure-key
   ```
3. Override the model to match the deployment name:
   ```bash
   uio agent run my-agent --model gpt-4o-production
   ```

Note: Azure routing requires specifying `--provider openai` or setting `default_provider = "openai"` in `uio.toml`, otherwise the Gemini key check may select Gemini first.

---

## Model override

To bypass tier selection entirely and use a specific model string:

```bash
uio agent run my-agent --model gemini-2.5-pro
uio chat --model gpt-4o-2024-11-20
```

`--model` is passed directly to the provider client. It overrides the `LLM_MODEL` env var, which in turn overrides the tier-based default.

Resolution order:

1. `--model` CLI flag
2. `LLM_MODEL` environment variable
3. Tier-based default (from `--complexity` / frontmatter / `[large_agents]`)

---

## Token cost reference

Costs are in USD per 1 million tokens (input / output).

| Provider | Model | Input ($/1M) | Output ($/1M) |
|---|---|---|---|
| `gemini` | `gemini-2.5-flash` | $0.15 | $0.60 |
| `gemini` | `gemini-2.5-flash-lite` | $0.10 | $0.40 |
| `anthropic` | `claude-sonnet-4-6` | $3.00 | $15.00 |
| `anthropic` | `claude-haiku-4-5-20251001` | $0.80 | $4.00 |
| `openai` | `gpt-4o` | $2.50 | $10.00 |
| `openai` | `gpt-4o-mini` | $0.15 | $0.60 |
| `ollama` | any | $0.00 | $0.00 |

These values come from `TOKEN_COSTS_PER_1M` in `uio/core/clients.py`. They reflect published pricing at the time of writing and may diverge from current provider pricing.

When a `--model` override is used with a model not in the table, cost estimation falls back to the provider-level entry if present, otherwise records $0.00.
