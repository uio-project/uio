"""LLM client abstractions: GeminiClient, OpenAIClient, OllamaClient."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import NamedTuple

from uio.core.tools import TOOL_SCHEMA, ToolCall

PROVIDER_DEFAULTS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o",
    "ollama": "llama3.1:8b",
}

PROVIDER_SMALL_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1:8b",
}

OLLAMA_BASE_URL = "http://localhost:11434/v1"

TOKEN_COSTS_PER_1M: dict[str, tuple[float, float]] = {
    "gemini/gemini-2.5-flash": (0.15, 0.60),
    "gemini/gemini-2.0-flash": (0.10, 0.40),
    "openai/gpt-4o": (2.50, 10.0),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "ollama": (0.0, 0.0),
}


class TokenUsage(NamedTuple):
    prompt_tokens: int
    completion_tokens: int


class LLMResponse(NamedTuple):
    text: str | None
    tool_calls: list[ToolCall]
    usage: TokenUsage | None = None


class LLMClient(ABC):
    @abstractmethod
    def build_history(self, user_text: str) -> list:
        """Return an initial message history containing the first user message."""

    @abstractmethod
    def chat(self, system: str, history: list) -> LLMResponse:
        """Send the conversation and return the model's response."""

    @abstractmethod
    def append_turn(
        self,
        history: list,
        response: LLMResponse,
        tool_results: list[tuple[ToolCall, str]],
    ) -> None:
        """Append a completed model turn (plus tool results) to the history."""


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
    def __init__(self, model: str | None = None, tools: list[dict] | None = None) -> None:
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

    def build_history(self, user_text: str) -> list:
        return [{"role": "user", "parts": [{"text": user_text}]}]

    def chat(self, system: str, history: list) -> LLMResponse:
        types = self._types
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=self._func_decls)],
        )
        resp = self._client.models.generate_content(
            model=self._model, config=config, contents=history
        )
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for part in resp.candidates[0].content.parts:
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

    def build_history(self, user_text: str) -> list:
        return [{"role": "user", "content": user_text}]

    def chat(self, system: str, history: list) -> LLMResponse:
        messages = [{"role": "system", "content": system}] + history
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=[{"type": "function", "function": t} for t in self._tools],
        )
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
) -> LLMClient:
    if provider == "gemini":
        return GeminiClient(model=model, tools=tools)
    if provider == "openai":
        return OpenAIClient(model=model, tools=tools, base_url=base_url)
    if provider == "ollama":
        return OllamaClient(model=model, tools=tools, base_url=base_url)
    raise ValueError(f"Unknown provider: {provider!r}. Supported: gemini, openai, ollama")
