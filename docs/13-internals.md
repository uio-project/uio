# Internals

This page describes the uio package architecture, what each module does, and how to extend the framework.

---

## Package layout

```
uio/
├── __init__.py              # version string
├── config.py                # uio.toml loader
├── examples.py              # bundled example definitions (embedded strings)
├── core/
│   ├── clients.py           # LLMClient ABC + provider implementations
│   ├── ledger.py            # cost estimation and JSONL append
│   ├── mcp.py               # MCP stdio client (JSON-RPC 2.0)
│   ├── routing.py           # provider auto-routing and model-tier selection
│   ├── runner.py            # main tool-use loop (run_agent)
│   └── tools.py             # run_command tool execution
├── cli/
│   ├── main.py              # root click group + init, validate, completion
│   ├── agent.py             # uio agent subcommands
│   ├── skill.py             # uio skill subcommands
│   ├── prompt.py            # uio prompt subcommands
│   ├── chat.py              # uio chat REPL with streaming
│   ├── cost.py              # uio cost command
│   ├── config.py            # uio config subcommands
│   ├── registry.py          # uio registry subcommands
│   └── _helpers.py          # shared list_definitions, print_definition_table
├── registry/
│   └── manifest.py          # manifest fetch, cache, search, install, validate
└── schema/
    └── parser.py            # YAML frontmatter parser and validator
```

---

## Layer-by-layer breakdown

### Definition layer — `uio/schema/parser.py`

`parse_definition_file(path)` reads a file, extracts the YAML frontmatter block (regex-matched between `---` delimiters), and returns `(frontmatter: dict, body: str)`.

A regex is used instead of a streaming YAML parser because frontmatter is always a small, bounded block at the top of the file — the rest is the body text that should not be parsed as YAML.

`validate_definition(path, frontmatter)` checks:
- `name` and `description` are present and non-empty (error if missing)
- All keys are in the known-keys set (warning if unknown)

Known keys: `name description complexity tools timeout argument-hint invokable`

---

### Config layer — `uio/config.py`

`load_config(path="uio.toml")` reads and merges `uio.toml` with built-in defaults. Uses `tomllib` from the standard library (Python 3.11+).

`_DEFAULTS` is the dict of built-in defaults. `load_config()` performs a shallow merge per section — values present in `uio.toml` override the corresponding defaults; missing sections fall back to defaults entirely.

`get_starter_toml()` returns the `_STARTER_TOML` string written by `uio config init`.

---

### Routing layer — `uio/core/routing.py`

`ROUTING_CHAIN = ["ollama", "openai", "gemini", "anthropic"]` — the auto-routing order.

`PROVIDER_KEY_ENV` maps each provider to its required API key env var (`None` for Ollama).

`infer_complexity(agent_name, frontmatter, override, large_names)` — returns `"large"` or `"small"`. Resolution order: CLI override → frontmatter `complexity:` → `large_names` list → default `"small"`.

`select_model(provider, complexity, model_override)` — returns the model string. Resolution order: `model_override` → `LLM_MODEL` env var → tier-based default from `PROVIDER_DEFAULTS` / `PROVIDER_SMALL_MODELS`.

`select_provider_chain(provider_override)` — if `provider_override` is set, returns `[provider_override]`. Otherwise returns all providers in `ROUTING_CHAIN` whose API key is set, with Ollama always included as the final fallback.

---

### Client layer — `uio/core/clients.py`

`LLMClient` is an abstract base class with three methods that all provider clients must implement:

- `build_history(user_text)` — returns an initial message history list containing the first user message, in the provider's native format
- `chat(system, history)` — sends the conversation to the LLM and returns `LLMResponse(text, tool_calls, usage)`
- `append_turn(history, response, tool_results)` — mutates the history list to append the model's response and the tool results, ready for the next turn

The three implementations:

- **`GeminiClient`** — uses `google.genai`. Message format uses `{"role": "user"/"model", "parts": [...]}`. Function calls use `FunctionDeclaration` and `Tool` types. Tool results use `function_response` parts.
- **`OpenAIClient`** — uses `openai`. Message format uses `{"role": "user"/"assistant"/"system"/"tool", "content": ...}`. Tool calls use the `tools` parameter with function JSON schemas. Supports `base_url` and `api_key` overrides.
- **`OllamaClient`** — subclasses `OpenAIClient` with a different base URL (`http://localhost:11434/v1`) and a dummy API key. Inherits the full OpenAI message format.

`make_client(provider, model, tools, base_url)` is the factory function.

`TOKEN_COSTS_PER_1M` is a dict mapping `"provider/model"` (or just `"provider"` as a fallback) to `(input_rate, output_rate)` tuples in USD per million tokens.

---

### Tools layer — `uio/core/tools.py`

`TOOL_SCHEMA` is the single JSON Schema for `run_command`:

```python
{
    "name": "run_command",
    "description": "Execute a shell command and return its stdout and stderr.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."}
        },
        "required": ["command"],
    },
}
```

`execute_tool(tc, *, mcp, timeout)` dispatches on tool name:
- `run_command` → `subprocess.run(command, shell=True, ...)` with output capped at 32,768 bytes and a configurable timeout (default 300s)
- `mcp__<server_name>__*` → forwarded to `MCPClient.call_tool()`
- Anything else → returns `"Unknown tool: <name>"`

`MAX_OUTPUT_BYTES = 32768`. Output that exceeds this is replaced with `"[output truncated]\n" + last_32k_bytes`.

---

### MCP layer — `uio/core/mcp.py`

`MCPClient` wraps a subprocess with stdin/stdout pipes. All communication is newline-delimited JSON (JSON-RPC 2.0).

Startup sequence:
1. `subprocess.Popen` with stdin/stdout pipes, stderr discarded
2. `_initialize()` — sends `initialize` RPC, waits for response, sends `initialized` notification
3. `list_tools()` — sends `tools/list` RPC, prefixes all tool names with `mcp__<server_name>__`
4. `call_tool(name, args)` — strips the prefix, sends `tools/call` RPC, joins text content parts

`_rpc(method, params)` is the blocking RPC primitive — it writes the request, then reads lines from stdout until it finds one with the matching `id`.

`make_mcp_client(server_name)` tries to start the GitHub MCP server via backwards-compat auto-start. Returns `None` on any failure (missing token, missing npx, process crash) and prints a warning to stderr.

`make_mcp_clients(mcp_cfg)` is the multi-server factory. It accepts the `[mcp]` section of the config (a `dict[str, dict]`) and returns a `dict[str, MCPClient]` keyed by server name. If `github` is absent from `mcp_cfg`, it calls `make_mcp_client()` for backwards compat. Servers that fail to start are warned and skipped; the rest proceed normally.

---

### Runner layer — `uio/core/runner.py`

`run_agent(agent_name, arg, provider, model, complexity, ...)` is the main entry point for all definition runs (agents, skills, and prompts share this function).

Execution flow:

1. Read and parse the definition file (`parse_definition_file`)
2. Build the provider chain (`select_provider_chain`)
3. Infer complexity and select model (`infer_complexity`, `select_model`)
4. Start MCP clients (`make_mcp_clients(mcp_cfg)`) — returns a `dict[str, MCPClient]`; empty when `--no-mcp` is passed
5. Build tool schema list (TOOL_SCHEMA + MCP tools, or empty list for prompts)
6. Inject the runtime preamble (`_PREAMBLE_SHELL_ONLY` or `_PREAMBLE_WITH_MCP`)
7. Build initial history with the user message (definition name + optional arg)
8. Enter the tool-use loop:
   - Call `client.chat(system, history)`
   - If no tool calls: print response, break
   - For each tool call: call `execute_tool`, collect results
   - Append turn to history (`client.append_turn`)
   - Repeat up to `max_iterations` (small, default 10) or `max_iterations_large` (large, default 25), configurable in `uio.toml` under `[runtime]`
9. Write cost ledger entry
10. Close MCP client

The loop is shared between agents and skills. Prompts bypass the loop: a single `client.chat()` call is made with an empty tool list, and the response is printed directly.

---

### Ledger layer — `uio/core/ledger.py`

`estimate_cost_usd(provider, model, prompt_tokens, completion_tokens)` looks up rates in `TOKEN_COSTS_PER_1M` using `"provider/model"` as the key, falling back to `"provider"`, then to `(0.0, 0.0)`.

`write_cost_ledger(agent_name, provider, model, ...)` builds the entry dict, opens the ledger file in append mode, and writes a JSON line. `OSError` is caught — write failures are non-fatal.

---

### Registry layer — `uio/registry/manifest.py`

`_raw_url(repo_url, ref, path)` converts a hosting URL to a raw file URL:
- `github.com` → `raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}`
- `gitlab.com` → `{base}/-/raw/{ref}/{path}`
- Anything else → `{url}/{ref}/{path}`

`fetch_manifest(registry, *, force, cache_dir)`:
1. Check if the cached file at `cache_dir/<name>.yaml` is fresh (based on `cache_ttl_hours`)
2. If fresh and not `force=True`, return the cached manifest
3. Fetch the manifest via `urllib.request.urlopen` with optional `Authorization` header (from `GITHUB_TOKEN`)
4. Write to cache, return parsed YAML
5. On network failure: return stale cache if it exists, otherwise raise `RuntimeError`

`search_definitions(registries, query, *, cache_dir)`:
- Iterates enabled registries, fetches each manifest
- Matches `query` (case-insensitive) against `name`, `description`, and each element of `tags`
- Injects `_registry: <name>` into each matched entry

`fetch_definition_content(registry, defn)` fetches a raw definition file via `_raw_url`. Raises `RuntimeError` on network failure.

`validate_manifest(manifest)` returns a list of error strings — checks `version`, `definitions` is a list, each entry has `name`/`type`/`path`/`description`, type is one of `agent`/`skill`/`prompt`.

`resolve_ref_to_sha(registry)` calls the GitHub API (`/repos/{owner}/{repo}/commits/{ref}`) and returns the SHA string. Returns `None` for non-GitHub URLs or network errors.

---

## Adding a new provider

1. **`uio/core/clients.py`** — Add a class that implements `LLMClient` (three methods: `build_history`, `chat`, `append_turn`). Add default and small model strings to `PROVIDER_DEFAULTS` and `PROVIDER_SMALL_MODELS`. Add cost rates to `TOKEN_COSTS_PER_1M`. Add a case to `make_client()`.

2. **`uio/core/routing.py`** — Add the provider name to `ROUTING_CHAIN` at the appropriate position. Add its key env var to `PROVIDER_KEY_ENV` (`None` if no key is needed).

3. **Tests** — Add message format tests to `tests/test_clients.py`. Add routing tests to `tests/test_routing.py`.

4. **Docs** — Add a section to [Providers](07-providers.md) and update the cost table.

---

## Adding a new tool

1. **`uio/core/tools.py`** — Add a JSON Schema entry (same shape as `TOOL_SCHEMA`) to the tool list. Add a dispatch branch in `execute_tool()`.

2. **`uio/cli/agent.py`** / **`uio/cli/chat.py`** — If the new tool requires an approval gate (like `run_command` does in the chat REPL), add the check in `_inner_tool_loop()` in `chat.py` and in the runner loop.

3. **Tests** — Add tests to `tests/test_tools.py`.

4. **Docs** — Document the tool in [Writing definitions](12-writing-definitions.md) under "Tool use patterns".

---

## Running the test suite

```bash
pytest
```

All 150+ tests run without API keys. Network calls are mocked via `unittest.mock.patch("urllib.request.urlopen")`. LLM calls are tested with mock client objects.

Test modules:

| File | What it covers |
|---|---|
| `tests/test_clients.py` | Message format per provider, `make_client` factory |
| `tests/test_routing.py` | Provider chain, model selection, `infer_complexity` |
| `tests/test_ledger.py` | Cost estimation, file append, `OSError` handling |
| `tests/test_parser.py` | Frontmatter edge cases, list-type fields, missing delimiters |
| `tests/test_tools.py` | `run_command` execution, timeout, output truncation, unknown tool |
| `tests/test_examples.py` | All bundled examples parse and pass `validate_definition` |
| `tests/test_registry.py` | URL normalisation, manifest cache/TTL, search, install, pin |

---

## Release process

The git tag is the single source of truth for the published version. `pyproject.toml` holds the placeholder `0.0.0.dev0` — it is never manually bumped.

When a `v*` tag is pushed, the `build` job in `release.yml`:

1. Strips the leading `v` and normalises to PEP 440 — `v0.1.0-rc3` → `0.1.0rc3`
2. Patches `pyproject.toml` in-place before building (CI only; the change is never committed)
3. Emits the normalised version as a job output consumed by `build-image`

**To cut a release:** push a tag — nothing else.

```bash
git tag v1.2.3          # stable release
git tag v1.2.3-rc1      # release candidate  →  1.2.3rc1 on PyPI
git tag v1.2.3-beta2    # beta               →  1.2.3b2 on PyPI
git push origin <tag>
```

Supported pre-release suffixes: `-rcN`, `-betaN`, `-alphaN`.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes.
3. Run the test suite: `pytest`
4. Format and lint: `ruff format . && ruff check .`
5. Open a pull request.

Guidelines:
- Keep tests offline — no API keys in CI. Mock all network and LLM calls.
- New user-visible behaviour requires a docs update in the relevant `docs/` page.
- New definition types (if ever added) require changes in `parser.py` (known fields), `cli/_helpers.py` (list support), and all affected docs pages.
- The two-persona documentation structure described in issue #5 applies to new docs: every page should serve both the newcomer and the experienced engineer.
