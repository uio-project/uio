"""Main tool-use loop for agents, skills, and prompts."""

from __future__ import annotations

import fnmatch
import glob as _glob
import os
import sys
import time

from uio import __version__
from uio.core.attribution import build_attribution_instructions
from uio.core.clients import make_client, probe_tool_calling
from uio.core.identities import KNOWN_ROLES
from uio.core.ledger import DEFAULT_LEDGER_PATH, estimate_cost_usd, write_cost_ledger
from uio.core.mcp import make_mcp_clients
from uio.core.memory import build_memory_section, clear_session_memory, estimate_tokens
from uio.core.routing import infer_complexity, select_model, select_provider_chain
from uio.core.tools import DEFAULT_TIMEOUT, TOOL_SCHEMA, execute_tool
from uio.core.vcs import build_tool_alias_section
from uio.schema.parser import parse_definition_file


class GuardrailError(Exception):
    """Raised when a per-definition guardrail limit is exceeded."""


class IdentityError(Exception):
    """Raised when VCS identity configuration or authentication fails."""


class ProviderExhaustedError(Exception):
    """Raised when all configured LLM providers have been tried and failed."""


_DEFAULT_MAX_ITERATIONS = 10
_DEFAULT_MAX_ITERATIONS_LARGE = 25

_RETRYABLE_SUBSTRINGS = (
    "503",
    "429",
    "UNAVAILABLE",
    "RESOURCE_EXHAUSTED",
    "Too Many Requests",
    "rate limit",
)
_MAX_CHAT_RETRIES = 3
_RETRY_BACKOFF = [5, 15, 30]  # seconds — enough for Gemini high-demand 503s to clear


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc)
    return any(s in msg for s in _RETRYABLE_SUBSTRINGS)


def _build_context_section(globs: list[str], project_root: str, max_tokens: int) -> str:
    """Resolve file globs and return a ## Context block for the system prompt.

    Files that match no globs are silently skipped.  Once the running token total
    reaches *max_tokens* the current file is truncated with a marker and no further
    files are read.  Returns an empty string when nothing matches.
    """
    if not globs:
        return ""

    sections: list[str] = []
    total_tokens = 0
    cap_reached = False
    seen: set[str] = set()

    for pattern in globs:
        if cap_reached:
            break
        matched = sorted(_glob.glob(os.path.join(project_root, pattern), recursive=True))
        for fpath in matched:
            if cap_reached:
                break
            if not os.path.isfile(fpath):
                continue
            real = os.path.realpath(fpath)
            if real in seen:
                continue
            seen.add(real)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue

            file_tokens = estimate_tokens(content)
            rel_path = os.path.relpath(fpath, project_root)
            remaining = max_tokens - total_tokens

            if file_tokens <= remaining:
                sections.append(f"### {rel_path}\n\n{content}")
                total_tokens += file_tokens
                if total_tokens >= max_tokens:
                    cap_reached = True
            else:
                cutoff = remaining * 4
                omitted = file_tokens - remaining
                sections.append(
                    f"### {rel_path}\n\n{content[:cutoff]}\n[truncated — {omitted} tokens omitted]"
                )
                cap_reached = True

    if not sections:
        return ""

    body = "\n\n---\n\n".join(sections)
    return f"## Context\n\n{body}\n\n"


def _inject_vcs_identity(frontmatter: dict) -> str | None:
    """Set credentials for a VCS identity agent; return the resolved role or None.

    Reads ``vcs-identity`` first; falls back to the deprecated ``github-identity``
    field with a warning.  When neither field is set this is a no-op.

    Only GitHub App authentication is implemented. Any other ``vcs-provider``
    value is rejected with a hard error.

    When a GitHub identity IS declared, App credentials are mandatory — no
    fallback to GITHUB_PERSONAL_ACCESS_TOKEN is permitted.
    """
    role = frontmatter.get("vcs-identity")
    if role is None:
        legacy = frontmatter.get("github-identity")
        if legacy:
            print(
                f"  [vcs-identity] Warning: 'github-identity' is deprecated —"
                f" use 'vcs-identity: {legacy}' instead.",
                file=sys.stderr,
            )
            role = legacy
    if not role:
        os.environ.pop("_UIO_APP_IDENTITY_ACTIVE", None)
        return None

    provider = frontmatter.get("vcs-provider", "github")

    if provider != "github":
        raise IdentityError(
            f"Error: vcs-provider '{provider}' is not supported — only 'github' is implemented.\n"
            f"  See docs/providers/ for the list of supported providers."
        )

    if role not in KNOWN_ROLES:
        raise IdentityError(
            f"Error: unsupported vcs-identity value '{role}' — must be one of {sorted(KNOWN_ROLES)}"
        )

    from uio.providers.github.app import (
        GitHubAppError,
        env_vars_present,
        get_token_for_identity,
    )

    if not env_vars_present(role):
        role_upper = role.upper()
        prefix = f"GITHUB_APP_{role_upper}_"
        missing = ", ".join(f"{prefix}{s}" for s in ("ID", "INSTALLATION_ID", "PRIVATE_KEY"))
        raise IdentityError(
            f"Error: 'vcs-identity: {role}' requires App credentials but env vars are not set.\n"
            f"  Missing: {missing}\n"
            f"  Falling back to GITHUB_PERSONAL_ACCESS_TOKEN is not permitted for identity agents.\n"
            f"  See docs/provisioning/ for setup instructions."
        )

    try:
        token = get_token_for_identity(role)
        os.environ["GH_TOKEN"] = token
        os.environ["_UIO_APP_IDENTITY_ACTIVE"] = "1"
        print(f"  [vcs-identity] authenticated as '{role}' GitHub App identity")
    except GitHubAppError as exc:
        raise IdentityError(
            f"Error: could not obtain GitHub App token for identity '{role}': {exc}\n"
            f"  Falling back to GITHUB_PERSONAL_ACCESS_TOKEN is not permitted for identity agents."
        ) from exc
    return role


def _build_preamble(
    has_mcp: bool,
    shell_override: str | None = None,
    vcs_provider: str | None = None,
) -> str:
    """Build the runtime preamble injected before the agent system prompt.

    shell_override (from --shell) takes precedence over platform auto-detection so
    the LLM is told the correct shell syntax regardless of the host OS.

    vcs_provider, when set, appends a VCS tool alias table so the LLM knows that
    ``vcs__*`` abstract names map to the active provider's MCP tool names.
    """
    shell_name = shell_override or ("PowerShell" if sys.platform == "win32" else "bash/sh")
    alias_section = build_tool_alias_section(vcs_provider) if vcs_provider else ""
    if has_mcp:
        return f"""\
## ℹ️ Runtime — Tools Available

You are running inside uio. Two tool families are available:

**`run_command`** — execute any shell command (gh CLI, kubectl, s3cmd, etc.)
Shell: {shell_name} — emit {shell_name}-style commands only.

**`mcp__<server>__*`** — native MCP tools (typed JSON, full API coverage).
Active servers and their tool prefixes are listed in the tool schema.
Prefer MCP tools over `run_command` equivalents when a matching server is available.

---
{alias_section}"""
    return f"""\
## ⚠️ Runtime — MCP Tools Unavailable

You are running inside uio. The ONLY tool available is `run_command`.

MCP tools (mcp__github__*, etc.) do NOT exist in this runtime.
Calling them will return "Unknown tool" and waste an iteration — do not attempt them.

For ALL GitHub operations, use `run_command` with the `gh` CLI.
Shell: {shell_name} — emit {shell_name}-style commands only.

---
{alias_section}"""


def run_agent(
    agent_name: str,
    arg: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    complexity: str | None = None,
    base_url: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    no_mcp: bool = False,
    mcp_cfg: dict | None = None,
    mcp_plugins: "list[dict] | None" = None,
    definition_path: str | None = None,
    ledger_path: str = DEFAULT_LEDGER_PATH,
    large_agent_names: list[str] | None = None,
    shell_override: str | None = None,
    max_iterations: int = _DEFAULT_MAX_ITERATIONS,
    max_iterations_large: int = _DEFAULT_MAX_ITERATIONS_LARGE,
    anthropic_max_tokens: int | None = None,
    routing_chain: list[str] | None = None,
    memory_dir: str | None = None,
    context_max_tokens: int = 8000,
    attribution_enabled: bool = True,
) -> str | None:
    if definition_path is None:
        raise ValueError("definition_path must be provided")
    if not os.path.exists(definition_path):
        raise ValueError(f"Error: definition not found at {definition_path}")

    frontmatter, body = parse_definition_file(definition_path)

    role = _inject_vcs_identity(frontmatter)

    mcp_clients: dict = {}
    if not no_mcp:
        mcp_clients = make_mcp_clients(mcp_cfg or {}, plugins=mcp_plugins)

    all_tools = [TOOL_SCHEMA]
    failed: list[str] = []
    for server_name, client in list(mcp_clients.items()):
        try:
            mcp_tools = client.list_tools()
            all_tools.extend(mcp_tools)
            print(f"  [mcp] '{server_name}' ready — {len(mcp_tools)} tools registered")
        except Exception as e:
            print(
                f"  [mcp] Warning: could not list tools for '{server_name}': {e}", file=sys.stderr
            )
            client.close()
            failed.append(server_name)
    for name in failed:
        del mcp_clients[name]

    # Inject the alias table when vcs-identity is set OR when capabilities includes "vcs".
    _caps = frontmatter.get("capabilities") or []
    if isinstance(_caps, str):
        _caps = [_caps]
    vcs_provider: str | None = None
    if role in KNOWN_ROLES or "vcs" in _caps:
        vcs_provider = frontmatter.get("vcs-provider", "github")

    preamble = _build_preamble(bool(mcp_clients), shell_override, vcs_provider)

    memory_block = build_memory_section(memory_dir) if memory_dir else ""
    memory_suffix = ("\n\n" + memory_block.rstrip()) if memory_block else ""

    context_globs = frontmatter.get("context") or []
    if isinstance(context_globs, str):
        context_globs = [context_globs]
    context_block = _build_context_section(context_globs, os.getcwd(), context_max_tokens)

    user_message = "Begin your workflow now."
    if arg:
        user_message = f"Begin your workflow now. Argument: {arg}"

    resolved_complexity = infer_complexity(agent_name, frontmatter, complexity, large_agent_names)
    provider_chain = select_provider_chain(provider, resolved_complexity, routing_chain)
    # Frontmatter max_tokens overrides the project-level anthropic_max_tokens setting.
    resolved_max_tokens: int | None = frontmatter.get("max_tokens") or anthropic_max_tokens

    guardrails = frontmatter.get("guardrails") or {}
    guardrail_max_cost: float | None = guardrails.get("max_cost_usd")
    guardrail_max_turns: int | None = guardrails.get("max_turns")
    guardrail_deny_tools: list[str] = guardrails.get("deny_tools") or []

    # max_turns from frontmatter takes precedence over the global cap.
    cap = (
        guardrail_max_turns
        if guardrail_max_turns is not None
        else (max_iterations_large if resolved_complexity == "large" else max_iterations)
    )

    _clean_exit = False
    _agent_header = f"# Agent: {frontmatter.get('name', agent_name)}\n\n{body}"
    try:
        last_error: Exception | None = None
        for candidate_provider in provider_chain:
            resolved_model = select_model(candidate_provider, resolved_complexity, model)

            attribution_block = (
                build_attribution_instructions(
                    role,
                    frontmatter.get("name", agent_name),
                    __version__,
                    vcs_provider or "github",
                    model=resolved_model,
                )
                if role in KNOWN_ROLES and attribution_enabled
                else ""
            )
            system_prompt = (
                f"{preamble}{attribution_block}{context_block}{_agent_header}{memory_suffix}"
            )

            try:
                client = make_client(
                    candidate_provider,
                    resolved_model,
                    tools=all_tools,
                    base_url=base_url,
                    complexity=resolved_complexity,
                    max_tokens=resolved_max_tokens,
                )
            except Exception as e:
                print(
                    f"  [router] {candidate_provider} init failed: {e}. Trying next...",
                    file=sys.stderr,
                )
                last_error = e
                continue

            if candidate_provider == "ollama" and not probe_tool_calling(client):
                print(
                    "  [router] ollama: tool-calling probe failed —"
                    " model does not return structured tool calls. Skipping.",
                    file=sys.stderr,
                )
                last_error = RuntimeError("ollama tool-calling probe failed")
                continue

            print(f"\n🤖 Agent: {frontmatter.get('name', agent_name)}")
            print(f"   Provider: {candidate_provider} / {resolved_model}  [{resolved_complexity}]")
            if arg:
                print(f"   Argument: {arg}")
            print()

            history = client.build_history(user_message)
            total_prompt = 0
            total_completion = 0

            try:
                for iteration in range(1, cap + 1):
                    print(f"[iteration {iteration}]")
                    for attempt in range(_MAX_CHAT_RETRIES):
                        try:
                            response = client.chat(system=system_prompt, history=history)
                            break
                        except Exception as e:
                            if _is_retryable(e) and attempt < _MAX_CHAT_RETRIES - 1:
                                wait = _RETRY_BACKOFF[attempt]
                                print(
                                    f"  [router] {candidate_provider} transient error"
                                    f" (attempt {attempt + 1}), retrying in {wait}s: {e}",
                                    file=sys.stderr,
                                )
                                time.sleep(wait)
                            else:
                                raise

                    if response.usage:
                        total_prompt += response.usage.prompt_tokens
                        total_completion += response.usage.completion_tokens

                    if response.text:
                        print(response.text)

                    if not response.tool_calls:
                        print("\n✅ Agent finished.")
                        write_cost_ledger(
                            agent_name,
                            candidate_provider,
                            resolved_model,
                            total_prompt,
                            total_completion,
                            ledger_path,
                        )
                        _clean_exit = True
                        return response.text or ""

                    if guardrail_max_cost is not None:
                        running_cost = estimate_cost_usd(
                            candidate_provider,
                            resolved_model,
                            total_prompt,
                            total_completion,
                        )
                        if running_cost > guardrail_max_cost:
                            write_cost_ledger(
                                agent_name,
                                candidate_provider,
                                resolved_model,
                                total_prompt,
                                total_completion,
                                ledger_path,
                            )
                            raise GuardrailError(
                                f"max_cost_usd {guardrail_max_cost} exceeded"
                                f" (running cost ${running_cost:.6f})"
                            )

                    tool_results = []
                    for tc in response.tool_calls:
                        denied = next(
                            (p for p in guardrail_deny_tools if fnmatch.fnmatch(tc.name, p)),
                            None,
                        )
                        if denied:
                            print(
                                f"  [guardrail] tool '{tc.name}' denied by deny_tools: {denied!r}"
                            )
                            tool_results.append(
                                (tc, f"[denied by guardrail deny_tools: {denied!r}]")
                            )
                        else:
                            tool_results.append(
                                (
                                    tc,
                                    execute_tool(
                                        tc,
                                        mcp_clients=mcp_clients,
                                        timeout=timeout,
                                        shell_override=shell_override,
                                    ),
                                )
                            )
                    client.append_turn(history, response, tool_results)

                print(f"\n⚠️  Reached iteration cap ({cap}). Stopping.")
                print(
                    f"   The agent did not finish. Increase max_iterations{'_large' if resolved_complexity == 'large' else ''}"
                    " in uio.toml or use --complexity to change the tier."
                )
                write_cost_ledger(
                    agent_name,
                    candidate_provider,
                    resolved_model,
                    total_prompt,
                    total_completion,
                    ledger_path,
                )
                _clean_exit = True
                return None

            except GuardrailError:
                raise
            except Exception as e:
                print(
                    f"  [router] {candidate_provider} failed mid-run: {e}. Trying next...",
                    file=sys.stderr,
                )
                last_error = e
                continue

        raise ProviderExhaustedError(f"Error: all providers exhausted. Last error: {last_error}")
    finally:
        for client in mcp_clients.values():
            client.close()
        if memory_dir and _clean_exit:
            clear_session_memory(memory_dir)
