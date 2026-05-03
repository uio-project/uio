"""uio chat — interactive streaming multi-turn REPL."""

from __future__ import annotations

import fnmatch
import json

import click

from uio.config import load_config
from uio.core.clients import (
    GeminiClient,
    LLMClient,
    LLMResponse,
    make_client,
    OpenAIClient,
    TokenUsage,
)
from uio.core.ledger import estimate_cost_usd, write_cost_ledger
from uio.core.routing import select_model, select_provider_chain
from uio.core.tools import TOOL_SCHEMA, ToolCall, execute_tool

_DEFAULT_SYSTEM = """\
You are a helpful AI assistant. Answer questions, help with code and debugging,
and assist with any development task. Be concise and direct.
"""

_MAX_TOOL_ITERS = 10

_SLASH_CMDS = {
    "/exit": "Exit the session",
    "/quit": "Exit the session",
    "/clear": "Clear conversation history",
    "/cost": "Show token spend for this session",
    "/help": "Show this help",
}


def _is_openai_compat(client: LLMClient) -> bool:
    return isinstance(client, OpenAIClient)  # OllamaClient subclasses OpenAIClient


def _is_gemini(client: LLMClient) -> bool:
    return isinstance(client, GeminiClient)


def _user_turn(client: LLMClient, text: str) -> dict:
    if _is_gemini(client):
        return {"role": "user", "parts": [{"text": text}]}
    return {"role": "user", "content": text}


def _assistant_turn(client: LLMClient, text: str | None) -> dict:
    safe = text or ""
    if _is_gemini(client):
        return {"role": "model", "parts": [{"text": safe}]}
    return {"role": "assistant", "content": safe}


def _stream_openai(client: LLMClient, system: str, history: list) -> LLMResponse:
    assert isinstance(client, OpenAIClient)
    messages = [{"role": "system", "content": system}] + history
    create_kwargs: dict = {
        "model": client._model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if client._tools:
        create_kwargs["tools"] = [{"type": "function", "function": t} for t in client._tools]

    stream = client._client.chat.completions.create(**create_kwargs)
    text_chunks: list[str] = []
    tc_acc: dict[int, dict] = {}
    usage: TokenUsage | None = None
    finish_reason: str | None = None

    for chunk in stream:
        if not chunk.choices:
            if hasattr(chunk, "usage") and chunk.usage:
                u = chunk.usage
                usage = TokenUsage(u.prompt_tokens, u.completion_tokens)
            continue
        choice = chunk.choices[0]
        delta = choice.delta
        if delta.content:
            click.echo(delta.content, nl=False)
            text_chunks.append(delta.content)
        if delta.tool_calls:
            for tc_chunk in delta.tool_calls:
                idx = tc_chunk.index
                if idx not in tc_acc:
                    tc_acc[idx] = {"id": "", "name": "", "args": ""}
                if tc_chunk.id:
                    tc_acc[idx]["id"] = tc_chunk.id
                if tc_chunk.function:
                    if tc_chunk.function.name:
                        tc_acc[idx]["name"] += tc_chunk.function.name
                    if tc_chunk.function.arguments:
                        tc_acc[idx]["args"] += tc_chunk.function.arguments
        finish_reason = choice.finish_reason or finish_reason
        if hasattr(chunk, "usage") and chunk.usage:
            u = chunk.usage
            usage = TokenUsage(u.prompt_tokens, u.completion_tokens)

    if text_chunks and finish_reason == "stop":
        click.echo()

    tool_calls: list[ToolCall] = []
    for idx in sorted(tc_acc):
        acc = tc_acc[idx]
        try:
            args = json.loads(acc["args"]) if acc["args"] else {}
        except json.JSONDecodeError:
            args = {}
        tool_calls.append(ToolCall(name=acc["name"], args=args, call_id=acc["id"]))

    return LLMResponse(text="".join(text_chunks) or None, tool_calls=tool_calls, usage=usage)


def _stream_gemini(client: LLMClient, system: str, history: list) -> LLMResponse:
    assert isinstance(client, GeminiClient)
    types = client._types
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=client._func_decls)],
    )
    text_chunks: list[str] = []
    calls: list[ToolCall] = []
    usage: TokenUsage | None = None

    for chunk in client._client.models.generate_content_stream(
        model=client._model, config=config, contents=history
    ):
        if not chunk.candidates:
            continue
        for part in chunk.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                click.echo(part.text, nl=False)
                text_chunks.append(part.text)
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                calls.append(ToolCall(name=fc.name, args=dict(fc.args), call_id=fc.name))
        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
            um = chunk.usage_metadata
            usage = TokenUsage(
                prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
            )

    if text_chunks:
        click.echo()
    return LLMResponse(text="".join(text_chunks) or None, tool_calls=calls, usage=usage)


def _stream_turn(client: LLMClient, system: str, history: list) -> LLMResponse:
    try:
        if _is_openai_compat(client):
            return _stream_openai(client, system, history)
        if _is_gemini(client):
            return _stream_gemini(client, system, history)
    except Exception as e:
        click.echo(f"\n  [stream error, retrying without streaming: {e}]", err=True)
    response = client.chat(system=system, history=history)
    if response.text:
        click.echo(response.text)
    return response


def _approval_gate(
    command: str,
    *,
    auto_approve: bool,
    allow_globs: tuple[str, ...],
    deny_globs: tuple[str, ...],
) -> bool:
    for pattern in deny_globs:
        if fnmatch.fnmatch(command, pattern):
            click.echo(f"  [denied by --deny {pattern!r}]", err=True)
            return False
    for pattern in allow_globs:
        if fnmatch.fnmatch(command, pattern):
            return True
    if auto_approve:
        return True
    try:
        answer = input(f"\n  $ {command}\n  Execute? [Y/n] ").strip().lower()
        return answer in ("", "y", "yes")
    except (EOFError, OSError):
        return False


def _inner_tool_loop(
    client: LLMClient,
    history: list,
    system: str,
    initial_response: LLMResponse,
    *,
    auto_approve: bool,
    allow_globs: tuple[str, ...],
    deny_globs: tuple[str, ...],
    timeout: int,
) -> tuple[LLMResponse, int, int]:
    extra_prompt = 0
    extra_completion = 0
    response = initial_response

    for _ in range(_MAX_TOOL_ITERS):
        if not response.tool_calls:
            break
        tool_results: list[tuple[ToolCall, str]] = []
        for tc in response.tool_calls:
            if tc.name == "run_command":
                command = tc.args.get("command", "")
                if not _approval_gate(
                    command,
                    auto_approve=auto_approve,
                    allow_globs=allow_globs,
                    deny_globs=deny_globs,
                ):
                    tool_results.append((tc, "[command rejected by user]"))
                    continue
            tool_results.append((tc, execute_tool(tc, timeout=timeout)))
        client.append_turn(history, response, tool_results)
        click.echo("\nAssistant: ", nl=False)
        response = _stream_turn(client, system, history)
        if response.usage:
            extra_prompt += response.usage.prompt_tokens
            extra_completion += response.usage.completion_tokens
    else:
        click.echo("\n  [warning: reached tool iteration cap]", err=True)

    return response, extra_prompt, extra_completion


def _show_session_cost(
    provider: str, model: str, prompt_tokens: int, completion_tokens: int
) -> None:
    total = prompt_tokens + completion_tokens
    cost = estimate_cost_usd(provider, model, prompt_tokens, completion_tokens)
    click.echo(
        f"  Session: {total:,} tokens "
        f"({prompt_tokens:,} in / {completion_tokens:,} out) — ${cost:.6f}"
    )


@click.command("chat")
@click.option(
    "--provider",
    default=None,
    help="LLM provider: gemini, openai, or ollama (default: auto-routes).",
)
@click.option("--model", default=None, help="Model name override.")
@click.option("--base-url", default=None, help="Base URL for an OpenAI-compatible endpoint.")
@click.option(
    "--system",
    "system_file",
    default=None,
    help="Path to a file whose contents become the system prompt.",
)
@click.option(
    "--tools",
    is_flag=True,
    default=False,
    help="Expose the run_command tool so the LLM can execute shell commands.",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    default=False,
    help="Skip per-command approval prompts (implies --tools).",
)
@click.option(
    "--allow",
    "allow_globs",
    multiple=True,
    metavar="GLOB",
    help="Shell-glob pattern for auto-approved commands (repeatable).",
)
@click.option(
    "--deny",
    "deny_globs",
    multiple=True,
    metavar="GLOB",
    help="Shell-glob pattern for always-rejected commands (repeatable).",
)
def chat_cmd(
    provider: str | None,
    model: str | None,
    base_url: str | None,
    system_file: str | None,
    tools: bool,
    auto_approve: bool,
    allow_globs: tuple[str, ...],
    deny_globs: tuple[str, ...],
) -> None:
    """Start an interactive streaming chat session.

    Examples:

    \b
      uio chat
      uio chat --provider ollama
      uio chat --tools
      uio chat --tools --allow 'git *' --auto-approve
    """
    cfg = load_config()
    if auto_approve:
        tools = True

    system = _DEFAULT_SYSTEM
    if system_file:
        try:
            with open(system_file) as f:
                system = f.read()
        except OSError as e:
            click.echo(f"Error reading --system file: {e}", err=True)
            raise SystemExit(1)

    tool_schemas = [TOOL_SCHEMA] if tools else []
    provider_chain = select_provider_chain(provider or cfg["runtime"].get("default_provider"))
    chosen_provider: str | None = None
    resolved_model: str | None = None
    client: LLMClient | None = None

    for candidate in provider_chain:
        resolved_model = select_model(candidate, "small", model)
        try:
            client = make_client(candidate, resolved_model, tools=tool_schemas, base_url=base_url)
            chosen_provider = candidate
            break
        except Exception as e:
            click.echo(f"  [router] {candidate} init failed: {e}.", err=True)

    if client is None or chosen_provider is None:
        click.echo("Error: all providers failed to initialize.", err=True)
        raise SystemExit(1)

    try:
        import readline  # noqa: F401
    except ImportError:
        pass

    tool_note = " +tools" if tools else ""
    click.echo(
        f"uio chat  [{chosen_provider}/{resolved_model}{tool_note}]\n"
        f"Type /help for commands, Ctrl-D or /exit to quit.\n"
    )

    history: list = []
    total_prompt = 0
    total_completion = 0

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break

        if not user_input:
            continue

        lower = user_input.lower()
        if lower in ("/exit", "/quit"):
            break
        if lower == "/clear":
            history.clear()
            click.echo("  [history cleared]\n")
            continue
        if lower == "/cost":
            _show_session_cost(chosen_provider, resolved_model, total_prompt, total_completion)
            click.echo()
            continue
        if lower == "/help":
            for cmd, desc in _SLASH_CMDS.items():
                click.echo(f"  {cmd:<8}  {desc}")
            click.echo()
            continue
        if user_input.startswith("/"):
            click.echo("  Unknown command. Type /help for available commands.\n")
            continue

        history.append(_user_turn(client, user_input))
        click.echo("\nAssistant: ", nl=False)
        try:
            response = _stream_turn(client, system, history)
        except KeyboardInterrupt:
            click.echo("\n  [interrupted]\n")
            history.pop()
            continue
        except Exception as e:
            click.echo(f"\n  [error] {e}\n", err=True)
            history.pop()
            continue

        if response.usage:
            total_prompt += response.usage.prompt_tokens
            total_completion += response.usage.completion_tokens

        if tools and response.tool_calls:
            response, ep, ec = _inner_tool_loop(
                client,
                history,
                system,
                response,
                auto_approve=auto_approve,
                allow_globs=allow_globs,
                deny_globs=deny_globs,
                timeout=cfg["runtime"]["timeout"],
            )
            total_prompt += ep
            total_completion += ec
            if response.usage:
                total_prompt += response.usage.prompt_tokens
                total_completion += response.usage.completion_tokens

        history.append(_assistant_turn(client, response.text or ""))
        click.echo()

    click.echo("\nSession ended.")
    if total_prompt + total_completion > 0:
        _show_session_cost(chosen_provider, resolved_model, total_prompt, total_completion)
        write_cost_ledger(
            "chat",
            chosen_provider,
            resolved_model,
            total_prompt,
            total_completion,
            cfg["runtime"]["cost_ledger"],
        )
