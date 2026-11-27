"""LLM client abstractions: GeminiClient, OpenAIClient, OllamaClient, AnthropicClient."""

from __future__ import annotations

import copy
import json
import os
import re
from abc import ABC, abstractmethod
from typing import NamedTuple

from uio.core.tools import TOOL_SCHEMA, ToolCall

PROVIDER_DEFAULTS = {
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4o",
    "ollama": "llama3.1:8b",
}

PROVIDER_SMALL_MODELS = {
    "gemini": "gemini-2.5-flash-lite",
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1:8b",
}

OLLAMA_BASE_URL = "http://localhost:11434/v1"

TOKEN_COSTS_PER_1M: dict[str, tuple[float, float]] = {
    "gemini/gemini-2.5-flash": (0.15, 0.60),
    "gemini/gemini-2.5-flash-lite": (0.10, 0.40),
    "anthropic/claude-fable-5-2": (8.00, 40.00),
    "anthropic/claude-opus-5-5": (4.00, 20.00),
    "anthropic/claude-sonnet-5-5": (2.00, 10.00),
    "anthropic/claude-haiku-5-5": (0.10, 0.50),
    "anthropic/claude-sonnet-4-6": (3.00, 15.00),
    "anthropic/claude-haiku-4-5-20251001": (0.80, 4.00),
    "openai/gpt-4o": (2.50, 10.0),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "ollama": (0.0, 0.0),
}


class TokenUsage(NamedTuple):
    """Tokens of one call. ``prompt_tokens`` counts the input billed at the full rate; a provider
    with prompt caching reports the input it read from its cache, and the input it wrote to it,
    apart, because each has its own price."""

    prompt_tokens: int
    completion_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class LLMResponse(NamedTuple):
    text: str | None
    tool_calls: list[ToolCall]
    usage: TokenUsage | None = None


class LLMClient(ABC):
    @abstractmethod
    def build_history(self, user_text: str) -> list:
        """Return an initial message history containing the first user message."""

    @abstractmethod
    def chat(self, system: str, history: list, tools_enabled: bool = True) -> LLMResponse:
        """Send the conversation and return the model's response.

        With ``tools_enabled`` False the model is told it may not call a tool this turn, so it
        answers in text: the runner's final turn at the iteration cap."""

    @abstractmethod
    def append_turn(
        self,
        history: list,
        response: LLMResponse,
        tool_results: list[tuple[ToolCall, str]],
    ) -> None:
        """Append a completed model turn (plus tool results) to the history."""

    def append_user_text(self, history: list, text: str) -> None:
        """Add a note from the runner as the user's next words."""
        history.append({"role": "user", "content": text})


_GEMINI_SCHEMA_DENYLIST = frozenset({"additionalProperties"})


def _sanitize_schema_for_gemini(schema: dict) -> dict:
    """Recursively strip fields the Gemini API rejects in tool schemas.

    Removes all dollar-prefixed JSON Schema meta-fields ($schema, $defs, $ref)
    and additionalProperties, which the Gemini API does not recognise.
    """
    result = {}
    for k, v in schema.items():
        if k.startswith("$") or k in _GEMINI_SCHEMA_DENYLIST:
            continue
        if isinstance(v, dict):
            result[k] = _sanitize_schema_for_gemini(v)
        elif isinstance(v, list):
            result[k] = [
                _sanitize_schema_for_gemini(item) if isinstance(item, dict) else item for item in v
            ]
        else:
            result[k] = v
    return result


class GeminiClient(LLMClient):
    def __init__(
        self,
        model: str | None = None,
        tools: list[dict] | None = None,
        output_schema: dict | None = None,
    ) -> None:
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self._model = model or os.environ.get("LLM_MODEL") or PROVIDER_DEFAULTS["gemini"]
        schemas = tools if tools is not None else [TOOL_SCHEMA]
        self._func_decls = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=_sanitize_schema_for_gemini(t["parameters"]),
            )
            for t in schemas
        ]
        self._output_schema: dict | None = output_schema

    def build_history(self, user_text: str) -> list:
        return [{"role": "user", "parts": [{"text": user_text}]}]

    def chat(self, system: str, history: list, tools_enabled: bool = True) -> LLMResponse:
        types = self._types
        config_kwargs: dict = {
            "system_instruction": system,
            "tools": [types.Tool(function_declarations=self._func_decls)],
        }
        if not tools_enabled:
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="NONE")
            )
        if self._output_schema is not None:
            config_kwargs.pop(
                "tools", None
            )  # response_schema and function_declarations are mutually exclusive
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = _sanitize_schema_for_gemini(self._output_schema)
        config = types.GenerateContentConfig(**config_kwargs)
        resp = self._client.models.generate_content(
            model=self._model, config=config, contents=history
        )
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for part in resp.candidates[0].content.parts or []:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)
            if hasattr(part, "function_call") and part.function_call:
                fc = part.function_call
                calls.append(ToolCall(name=fc.name, args=dict(fc.args), call_id=fc.name))
        usage: TokenUsage | None = None
        if hasattr(resp, "usage_metadata") and resp.usage_metadata:
            um = resp.usage_metadata
            usage = TokenUsage(
                prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
                completion_tokens=getattr(um, "candidates_token_count", 0) or 0,
            )
        return LLMResponse(text="\n".join(text_parts) or None, tool_calls=calls, usage=usage)

    def append_user_text(self, history: list, text: str) -> None:
        history.append({"role": "user", "parts": [{"text": text}]})

    def append_turn(
        self,
        history: list,
        response: LLMResponse,
        tool_results: list[tuple[ToolCall, str]],
    ) -> None:
        model_parts: list[dict] = []
        if response.text:
            model_parts.append({"text": response.text})
        for tc in response.tool_calls:
            model_parts.append({"function_call": {"name": tc.name, "args": tc.args}})
        history.append({"role": "model", "parts": model_parts})
        if tool_results:
            history.append(
                {
                    "role": "user",
                    "parts": [
                        {"function_response": {"name": tc.name, "response": {"output": out}}}
                        for tc, out in tool_results
                    ],
                }
            )


class OpenAIClient(LLMClient):
    def __init__(
        self,
        model: str | None = None,
        tools: list[dict] | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        output_schema: dict | None = None,
    ) -> None:
        import openai

        kwargs: dict = {}
        effective_base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        if effective_base_url:
            kwargs["base_url"] = effective_base_url
        if api_key:
            kwargs["api_key"] = api_key
        self._client = openai.OpenAI(**kwargs)
        self._model = model or os.environ.get("LLM_MODEL") or PROVIDER_DEFAULTS["openai"]
        self._tools = tools if tools is not None else [TOOL_SCHEMA]
        self._output_schema: dict | None = output_schema

    def build_history(self, user_text: str) -> list:
        return [{"role": "user", "content": user_text}]

    def chat(self, system: str, history: list, tools_enabled: bool = True) -> LLMResponse:
        messages = [{"role": "system", "content": system}] + history
        create_kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "tools": [{"type": "function", "function": t} for t in self._tools],
        }
        if not tools_enabled:
            create_kwargs["tool_choice"] = "none"
        if self._output_schema is not None:
            create_kwargs.pop(
                "tools", None
            )  # structured output and tool-calling are mutually exclusive
            create_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "schema": self._output_schema,
                    "strict": True,
                },
            }
        resp = self._client.chat.completions.create(**create_kwargs)
        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                calls.append(
                    ToolCall(
                        name=tc.function.name,
                        args=json.loads(tc.function.arguments),
                        call_id=tc.id,
                    )
                )
        usage: TokenUsage | None = None
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.prompt_tokens,
                completion_tokens=resp.usage.completion_tokens,
            )
        return LLMResponse(text=msg.content, tool_calls=calls, usage=usage)

    def append_turn(
        self,
        history: list,
        response: LLMResponse,
        tool_results: list[tuple[ToolCall, str]],
    ) -> None:
        history.append(
            {
                "role": "assistant",
                "content": response.text,
                "tool_calls": [
                    {
                        "id": tc.call_id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                    }
                    for tc in response.tool_calls
                ]
                or None,
            }
        )
        for tc, out in tool_results:
            history.append({"role": "tool", "tool_call_id": tc.call_id, "content": out})


def _to_anthropic_tool(tool: dict) -> dict:
    """Convert an OpenAI-style tool schema to Anthropic's {name, description, input_schema} shape."""
    return {
        "name": tool["name"],
        "description": tool["description"],
        "input_schema": tool["parameters"],
    }


_ANTHROPIC_DEFAULT_MAX_TOKENS = 16000

# Claude 4.6 and later take adaptive thinking; from 4.7 on a `budget_tokens` request is refused.
# A dated id (claude-opus-4-20250514) has no minor version: its date is not one.
_CLAUDE_VERSION = re.compile(
    r"claude-(?:opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d{1,2}))?(?:-|$)"
)
_CACHE = {"type": "ephemeral"}


def uses_adaptive_thinking(model: str) -> bool:
    """Whether ``model`` takes adaptive thinking. A name this cannot read, such as a gateway's
    own alias, is taken to be a current model."""
    match = _CLAUDE_VERSION.search(model)
    if not match:
        return True
    return (int(match.group(1)), int(match.group(2) or 0)) >= (4, 6)


def with_cache_breakpoint(history: list) -> list:
    """The history with a cache breakpoint on the newest message, which is copied, so the stored
    history never carries one. Each turn then reads everything before it from the cache."""
    if not history:
        return history
    last = copy.deepcopy(history[-1])
    content = last.get("content")
    if isinstance(content, str):
        last["content"] = [{"type": "text", "text": content, "cache_control": _CACHE}]
    elif isinstance(content, list) and content and isinstance(content[-1], dict):
        content[-1]["cache_control"] = _CACHE
    return [*history[:-1], last]


def serialize_anthropic_block(block) -> dict:
    """Convert an Anthropic SDK content block to a plain dict for history storage."""
    if block.type == "text":
        return {"type": "text", "text": block.text}
    if block.type == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    if block.type == "thinking":
        return {"type": "thinking", "thinking": block.thinking, "signature": block.signature}
    if block.type == "redacted_thinking":
        return {"type": "redacted_thinking", "data": block.data}
    return {"type": block.type}


class AnthropicClient(LLMClient):
    def __init__(
        self,
        model: str | None = None,
        tools: list[dict] | None = None,
        complexity: str | None = None,
        max_tokens: int | None = None,
        base_url: str | None = None,
    ) -> None:
        import anthropic

        # The SDK reads ANTHROPIC_API_KEY, or ANTHROPIC_AUTH_TOKEN for a bearer token, and
        # ANTHROPIC_BASE_URL itself; --base-url wins over the variable.
        self._client = anthropic.Anthropic(**({"base_url": base_url} if base_url else {}))
        self._model = model or os.environ.get("LLM_MODEL") or PROVIDER_DEFAULTS["anthropic"]
        schemas = tools if tools is not None else [TOOL_SCHEMA]
        self._tools = [_to_anthropic_tool(t) for t in schemas]
        self._complexity = complexity or "small"
        self._max_tokens = max_tokens or _ANTHROPIC_DEFAULT_MAX_TOKENS
        self._last_raw_content: list[dict] = []

    def build_history(self, user_text: str) -> list:
        return [{"role": "user", "content": user_text}]

    def chat(self, system: str, history: list, tools_enabled: bool = True) -> LLMResponse:
        kwargs: dict = {}
        if self._complexity == "large":
            if uses_adaptive_thinking(self._model):
                kwargs["thinking"] = {"type": "adaptive"}
            else:
                budget = min(10000, max(1024, self._max_tokens - 4096))
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
        if not tools_enabled:
            kwargs["tool_choice"] = {"type": "none"}
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            # The tools and the system prompt are the same every turn: cached once, read after.
            system=[{"type": "text", "text": system, "cache_control": _CACHE}],
            tools=self._tools,
            messages=with_cache_breakpoint(history),
            **kwargs,
        )
        self._last_raw_content = [serialize_anthropic_block(b) for b in resp.content]
        text = next((b.text for b in resp.content if b.type == "text"), None)
        calls = [
            ToolCall(name=b.name, args=b.input, call_id=b.id)
            for b in resp.content
            if b.type == "tool_use"
        ]
        usage: TokenUsage | None = None
        if resp.usage:
            usage = TokenUsage(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
                cache_read_tokens=getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
            )
        return LLMResponse(text=text, tool_calls=calls, usage=usage)

    def append_turn(
        self,
        history: list,
        response: LLMResponse,
        tool_results: list[tuple[ToolCall, str]],
    ) -> None:
        # When thinking blocks are present they must be round-tripped as-is.
        # Use stored raw content if available; otherwise build from response fields.
        raw = getattr(self, "_last_raw_content", None)
        if raw:
            content = list(raw)
        else:
            content = []
            if response.text:
                content.append({"type": "text", "text": response.text})
            for tc in response.tool_calls:
                content.append(
                    {"type": "tool_use", "id": tc.call_id, "name": tc.name, "input": tc.args}
                )
        history.append({"role": "assistant", "content": content})
        if tool_results:
            history.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": tc.call_id, "content": out}
                        for tc, out in tool_results
                    ],
                }
            )

    def append_user_text(self, history: list, text: str) -> None:
        # The roles alternate: after tool results the note joins that user turn.
        if history and history[-1].get("role") == "user":
            content = history[-1]["content"]
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            history[-1]["content"] = [*content, {"type": "text", "text": text}]
        else:
            history.append({"role": "user", "content": text})


class OllamaClient(OpenAIClient):
    """OpenAI-compatible client targeting a local Ollama instance."""

    def __init__(
        self,
        model: str | None = None,
        tools: list[dict] | None = None,
        base_url: str | None = None,
    ) -> None:
        effective_url = base_url or os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL)
        effective_key = os.environ.get("OPENAI_API_KEY", "ollama")
        super().__init__(
            model=model or PROVIDER_DEFAULTS["ollama"],
            tools=tools,
            base_url=effective_url,
            api_key=effective_key,
        )


def probe_tool_calling(client: LLMClient) -> bool:
    """Return True if the client correctly returns a structured ToolCall.

    Used to verify Ollama models honour the OpenAI function-calling spec before
    committing them to a multi-step agentic run.
    """
    try:
        history = client.build_history("Call run_command with command='echo probe'")
        response = client.chat(
            system="You are a tool caller. Always call tools when asked.", history=history
        )
        return len(response.tool_calls) > 0
    except Exception:
        return False


def make_client(
    provider: str,
    model: str | None = None,
    tools: list[dict] | None = None,
    base_url: str | None = None,
    complexity: str | None = None,
    max_tokens: int | None = None,
    output_schema: dict | None = None,
) -> LLMClient:
    if provider == "gemini":
        return GeminiClient(model=model, tools=tools, output_schema=output_schema)
    if provider == "anthropic":
        return AnthropicClient(
            model=model,
            tools=tools,
            complexity=complexity,
            max_tokens=max_tokens,
            base_url=base_url,
        )
    if provider == "openai":
        return OpenAIClient(
            model=model, tools=tools, base_url=base_url, output_schema=output_schema
        )
    if provider == "ollama":
        return OllamaClient(model=model, tools=tools, base_url=base_url)
    raise ValueError(
        f"Unknown provider: {provider!r}. Supported: gemini, anthropic, openai, ollama"
    )
