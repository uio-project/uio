"""Tests for GeminiClient and OpenAIClient append_turn message formatting.

Instances are created via __new__ to skip __init__ (which requires API keys).
Only append_turn and build_history are under test — pure message formatting.
"""

import json


from uio.core.clients import GeminiClient, LLMResponse, OpenAIClient, _sanitize_schema_for_gemini
from uio.core.tools import ToolCall


def tc(cmd: str = "echo hi", call_id: str = "tc-1") -> ToolCall:
    return ToolCall(name="run_command", args={"command": cmd}, call_id=call_id)


# ── GeminiClient ──────────────────────────────────────────────────────────────


def gemini() -> GeminiClient:
    return GeminiClient.__new__(GeminiClient)


def test_gemini_text_only_appends_model_turn():
    client = gemini()
    history = [{"role": "user", "parts": [{"text": "begin"}]}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    assert len(history) == 2
    assert history[1] == {"role": "model", "parts": [{"text": "Done."}]}


def test_gemini_no_extra_user_turn_when_no_tools():
    client = gemini()
    history = [{"role": "user", "parts": [{"text": "begin"}]}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    assert all(t["role"] != "user" or t == history[0] for t in history)


def test_gemini_tool_result_appended_as_user_turn():
    client = gemini()
    history = [{"role": "user", "parts": [{"text": "begin"}]}]
    call = tc()
    client.append_turn(history, LLMResponse(text=None, tool_calls=[call]), [(call, "hi\n")])

    assert len(history) == 3
    model_turn = history[1]
    assert model_turn["role"] == "model"
    assert {"function_call": {"name": "run_command", "args": {"command": "echo hi"}}} in model_turn[
        "parts"
    ]

    tool_turn = history[2]
    assert tool_turn["role"] == "user"
    part = tool_turn["parts"][0]["function_response"]
    assert part["name"] == "run_command"
    assert part["response"]["output"] == "hi\n"


def test_gemini_multiple_tool_results_packed_into_one_user_turn():
    client = gemini()
    history = [{"role": "user", "parts": [{"text": "begin"}]}]
    c1 = tc("echo a", "tc-1")
    c2 = tc("echo b", "tc-2")
    client.append_turn(
        history,
        LLMResponse(text=None, tool_calls=[c1, c2]),
        [(c1, "a\n"), (c2, "b\n")],
    )
    assert len(history) == 3  # user + model + one combined user turn
    assert len(history[2]["parts"]) == 2


def test_gemini_text_and_tool_call_both_in_model_parts():
    client = gemini()
    history = [{"role": "user", "parts": [{"text": "begin"}]}]
    call = tc()
    client.append_turn(history, LLMResponse(text="Running...", tool_calls=[call]), [(call, "out")])
    model_parts = history[1]["parts"]
    assert {"text": "Running..."} in model_parts
    assert any("function_call" in p for p in model_parts)


# ── OpenAIClient ──────────────────────────────────────────────────────────────


def openai_client() -> OpenAIClient:
    return OpenAIClient.__new__(OpenAIClient)


def test_openai_text_only_appends_assistant_turn():
    client = openai_client()
    history = [{"role": "user", "content": "begin"}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    assert len(history) == 2
    assert history[1] == {"role": "assistant", "content": "Done.", "tool_calls": None}


def test_openai_tool_result_appended_as_tool_turn():
    client = openai_client()
    history = [{"role": "user", "content": "begin"}]
    call = tc(call_id="tc-1")
    client.append_turn(history, LLMResponse(text=None, tool_calls=[call]), [(call, "hi\n")])

    assert len(history) == 3
    assistant = history[1]
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"][0]["id"] == "tc-1"
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"command": "echo hi"}

    tool = history[2]
    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "tc-1"
    assert tool["content"] == "hi\n"


def test_openai_multiple_tool_calls_each_get_own_turn():
    client = openai_client()
    history = [{"role": "user", "content": "begin"}]
    c1 = tc("echo a", "tc-1")
    c2 = tc("echo b", "tc-2")
    client.append_turn(
        history,
        LLMResponse(text=None, tool_calls=[c1, c2]),
        [(c1, "a\n"), (c2, "b\n")],
    )
    assert len(history) == 4  # user + assistant + tool-1 + tool-2
    assert history[2]["tool_call_id"] == "tc-1"
    assert history[3]["tool_call_id"] == "tc-2"


def test_openai_assistant_tool_calls_serialised_as_json():
    client = openai_client()
    history = [{"role": "user", "content": "begin"}]
    call = tc(cmd="ls -la", call_id="tc-x")
    client.append_turn(history, LLMResponse(text=None, tool_calls=[call]), [(call, "out")])
    raw_args = history[1]["tool_calls"][0]["function"]["arguments"]
    assert json.loads(raw_args) == {"command": "ls -la"}


# ── _sanitize_schema_for_gemini ───────────────────────────────────────────────


def test_sanitize_strips_dollar_schema():
    params = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {"x": {"type": "string"}},
    }
    result = _sanitize_schema_for_gemini(params)
    assert "$schema" not in result
    assert result["type"] == "object"


def test_sanitize_strips_additional_properties():
    params = {"type": "object", "additionalProperties": False, "properties": {}}
    result = _sanitize_schema_for_gemini(params)
    assert "additionalProperties" not in result
    assert result["type"] == "object"


def test_sanitize_strips_fields_recursively():
    params = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string", "additionalProperties": False},
            }
        },
        "additionalProperties": False,
    }
    result = _sanitize_schema_for_gemini(params)
    assert "additionalProperties" not in result
    assert "additionalProperties" not in result["properties"]["items"]["items"]


def test_sanitize_strips_inside_anyof():
    params = {
        "anyOf": [
            {"type": "string", "$ref": "#/defs/Foo", "additionalProperties": False},
            {"type": "null"},
        ]
    }
    result = _sanitize_schema_for_gemini(params)
    assert "$ref" not in result["anyOf"][0]
    assert "additionalProperties" not in result["anyOf"][0]
    assert result["anyOf"][1] == {"type": "null"}


def test_sanitize_passthrough_clean_schema():
    params = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
    assert _sanitize_schema_for_gemini(params) == params
