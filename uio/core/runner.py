"""Main tool-use loop for agents, skills, and prompts."""

from __future__ import annotations

import os
import sys

from uio.core.clients import make_client
from uio.core.ledger import DEFAULT_LEDGER_PATH, write_cost_ledger
from uio.core.mcp import make_mcp_clients
from uio.core.routing import infer_complexity, select_model, select_provider_chain
from uio.core.tools import DEFAULT_TIMEOUT, TOOL_SCHEMA, execute_tool
from uio.schema.parser import parse_definition_file

MAX_ITERATIONS = 10

_PREAMBLE_SHELL_ONLY = """\
## ⚠️ Runtime — MCP Tools Unavailable

You are running inside uio. The ONLY tool available is `run_command`.

MCP tools (mcp__github__*, etc.) do NOT exist in this runtime.
Calling them will return "Unknown tool" and waste an iteration — do not attempt them.

For ALL GitHub operations, use `run_command` with the `gh` CLI.

---
"""

_PREAMBLE_WITH_MCP = """\
## ℹ️ Runtime — Tools Available

You are running inside uio. Two tool families are available:

**`run_command`** — execute any shell command (gh CLI, kubectl, s3cmd, etc.)

**`mcp__<server>__*`** — native MCP tools (typed JSON, full API coverage).
Active servers and their tool prefixes are listed in the tool schema.
Prefer MCP tools over `run_command` equivalents when a matching server is available.

---
"""


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
    definition_path: str | None = None,
    ledger_path: str = DEFAULT_LEDGER_PATH,
    large_agent_names: list[str] | None = None,
) -> None:
    if definition_path is None:
        raise ValueError("definition_path must be provided")
    if not os.path.exists(definition_path):
        sys.exit(f"Error: definition not found at {definition_path}")

    frontmatter, body = parse_definition_file(definition_path)

    mcp_clients: dict = {}
    if not no_mcp:
        mcp_clients = make_mcp_clients(mcp_cfg or {})

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

    preamble = _PREAMBLE_WITH_MCP if mcp_clients else _PREAMBLE_SHELL_ONLY
    system_prompt = f"{preamble}# Agent: {frontmatter.get('name', agent_name)}\n\n{body}"

    user_message = "Begin your workflow now."
    if arg:
        user_message = f"Begin your workflow now. Argument: {arg}"

    resolved_complexity = infer_complexity(agent_name, frontmatter, complexity, large_agent_names)
    provider_chain = select_provider_chain(provider)

    try:
        last_error: Exception | None = None
        for candidate_provider in provider_chain:
            resolved_model = select_model(candidate_provider, resolved_complexity, model)
            try:
                client = make_client(
                    candidate_provider, resolved_model, tools=all_tools, base_url=base_url
                )
            except Exception as e:
                print(
                    f"  [router] {candidate_provider} init failed: {e}. Trying next...",
                    file=sys.stderr,
                )
                last_error = e
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
                for iteration in range(1, MAX_ITERATIONS + 1):
                    print(f"[iteration {iteration}]")
                    response = client.chat(system=system_prompt, history=history)

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
                        return

                    tool_results = [
                        (tc, execute_tool(tc, mcp_clients=mcp_clients, timeout=timeout))
                        for tc in response.tool_calls
                    ]
                    client.append_turn(history, response, tool_results)

                print(f"\n⚠️  Reached iteration cap ({MAX_ITERATIONS}). Stopping.")
                write_cost_ledger(
                    agent_name,
                    candidate_provider,
                    resolved_model,
                    total_prompt,
                    total_completion,
                    ledger_path,
                )
                return

            except Exception as e:
                print(
                    f"  [router] {candidate_provider} failed mid-run: {e}. Trying next...",
                    file=sys.stderr,
                )
                last_error = e
                continue

        sys.exit(f"Error: all providers exhausted. Last error: {last_error}")
    finally:
        for client in mcp_clients.values():
            client.close()
