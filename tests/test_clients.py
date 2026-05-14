"""Tests for GeminiClient, OpenAIClient, and AnthropicClient message formatting.

Instances are created via __new__ to skip __init__ (which requires API keys).
Only append_turn and build_history are under test — pure message formatting.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


from uio.core.clients import (
    AnthropicClient,
    GeminiClient,
    LLMResponse,
    OpenAIClient,
    _ANTHROPIC_DEFAULT_MAX_TOKENS,
    _sanitize_schema_for_gemini,
    serialize_anthropic_block,
    _to_anthropic_tool,
)
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


# ── _to_anthropic_tool ────────────────────────────────────────────────────────


def test_to_anthropic_tool_converts_schema():
    tool = {
        "name": "run_command",
        "description": "Execute a shell command.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}},
    }
    result = _to_anthropic_tool(tool)
    assert result["name"] == "run_command"
    assert result["description"] == "Execute a shell command."
    assert result["input_schema"] == tool["parameters"]
    assert "parameters" not in result


# ── AnthropicClient ───────────────────────────────────────────────────────────


def anthropic_client() -> AnthropicClient:
    return AnthropicClient.__new__(AnthropicClient)


def test_anthropic_build_history():
    client = anthropic_client()
    history = client.build_history("hello")
    assert history == [{"role": "user", "content": "hello"}]


def test_anthropic_text_only_appends_assistant_turn():
    client = anthropic_client()
    history = [{"role": "user", "content": "begin"}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    assert len(history) == 2
    assert history[1] == {"role": "assistant", "content": [{"type": "text", "text": "Done."}]}


def test_anthropic_no_extra_user_turn_when_no_tools():
    client = anthropic_client()
    history = [{"role": "user", "content": "begin"}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    assert len(history) == 2


def test_anthropic_tool_call_in_assistant_content():
    client = anthropic_client()
    history = [{"role": "user", "content": "begin"}]
    call = tc(call_id="toolu_01")
    client.append_turn(history, LLMResponse(text=None, tool_calls=[call]), [(call, "output\n")])

    assert len(history) == 3
    asst = history[1]
    assert asst["role"] == "assistant"
    assert {
        "type": "tool_use",
        "id": "toolu_01",
        "name": "run_command",
        "input": {"command": "echo hi"},
    } in asst["content"]

    user_turn = history[2]
    assert user_turn["role"] == "user"
    assert user_turn["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_01", "content": "output\n"}
    ]


def test_anthropic_multiple_tool_results_in_one_user_turn():
    client = anthropic_client()
    history = [{"role": "user", "content": "begin"}]
    c1 = tc("echo a", "toolu_01")
    c2 = tc("echo b", "toolu_02")
    client.append_turn(
        history,
        LLMResponse(text=None, tool_calls=[c1, c2]),
        [(c1, "a\n"), (c2, "b\n")],
    )
    assert len(history) == 3
    assert len(history[2]["content"]) == 2
    assert history[2]["content"][0]["tool_use_id"] == "toolu_01"
    assert history[2]["content"][1]["tool_use_id"] == "toolu_02"


def test_anthropic_text_and_tool_call_both_in_assistant_content():
    client = anthropic_client()
    history = [{"role": "user", "content": "begin"}]
    call = tc(call_id="toolu_01")
    client.append_turn(history, LLMResponse(text="Running...", tool_calls=[call]), [(call, "out")])
    content = history[1]["content"]
    assert {"type": "text", "text": "Running..."} in content
    assert any(b.get("type") == "tool_use" for b in content)


def test_anthropic_append_turn_uses_raw_content_when_present():
    client = anthropic_client()
    # Simulate raw content stored after chat() with a thinking block
    client._last_raw_content = [
        {"type": "thinking", "thinking": "my reasoning", "signature": "sig_abc"},
        {"type": "text", "text": "Done."},
    ]
    history = [{"role": "user", "content": "begin"}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    content = history[1]["content"]
    assert content == [
        {"type": "thinking", "thinking": "my reasoning", "signature": "sig_abc"},
        {"type": "text", "text": "Done."},
    ]


def test_anthropic_append_turn_without_raw_content_falls_back_to_response():
    client = anthropic_client()
    # No _last_raw_content set (e.g. bypassed __init__ via __new__)
    history = [{"role": "user", "content": "begin"}]
    client.append_turn(history, LLMResponse(text="Done.", tool_calls=[]), [])
    assert history[1]["content"] == [{"type": "text", "text": "Done."}]


# ── serialize_anthropic_block ─────────────────────────────────────────────────


def _block(type_: str, **kwargs):
    return SimpleNamespace(type=type_, **kwargs)


def test_serialize_text_block():
    block = _block("text", text="hello")
    assert serialize_anthropic_block(block) == {"type": "text", "text": "hello"}


def test_serialize_tool_use_block():
    block = _block("tool_use", id="toolu_01", name="run_command", input={"command": "ls"})
    result = serialize_anthropic_block(block)
    assert result == {
        "type": "tool_use",
        "id": "toolu_01",
        "name": "run_command",
        "input": {"command": "ls"},
    }


def test_serialize_thinking_block():
    block = _block("thinking", thinking="I think...", signature="sig_xyz")
    result = serialize_anthropic_block(block)
    assert result == {"type": "thinking", "thinking": "I think...", "signature": "sig_xyz"}


def test_serialize_redacted_thinking_block():
    block = _block("redacted_thinking", data="<redacted>")
    assert serialize_anthropic_block(block) == {"type": "redacted_thinking", "data": "<redacted>"}


def test_serialize_unknown_block_type():
    block = _block("future_type")
    assert serialize_anthropic_block(block) == {"type": "future_type"}


# ── AnthropicClient max_tokens / complexity ───────────────────────────────────


def test_anthropic_default_max_tokens():
    assert _ANTHROPIC_DEFAULT_MAX_TOKENS == 16000


def test_anthropic_client_stores_complexity_and_max_tokens():
    client = AnthropicClient.__new__(AnthropicClient)
    client._complexity = "large"
    client._max_tokens = 32000
    assert client._complexity == "large"
    assert client._max_tokens == 32000


# ── output_schema: create_kwargs / config_kwargs injection ───────────────────

_SAMPLE_SCHEMA = {"type": "object", "properties": {"result": {"type": "string"}}}


def test_openai_chat_with_output_schema_injects_response_format():
    """chat() adds response_format and drops tools when output_schema is set."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = '{"result": "ok"}'
    mock_resp.choices[0].message.tool_calls = None
    mock_resp.usage = None

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_completions = MagicMock()
        mock_completions.create.return_value = mock_resp
        mock_openai_cls.return_value.chat.completions = mock_completions

        client = OpenAIClient(output_schema=_SAMPLE_SCHEMA)
        client.chat(system="sys", history=[{"role": "user", "content": "go"}])

        _, kwargs = mock_completions.create.call_args
        assert "response_format" in kwargs
        assert kwargs["response_format"]["type"] == "json_schema"
        assert kwargs["response_format"]["json_schema"]["strict"] is True
        assert "tools" not in kwargs, "tools must be omitted when output_schema is set"


def test_openai_chat_without_output_schema_includes_tools():
    """chat() includes tools and no response_format when output_schema is None."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "hello"
    mock_resp.choices[0].message.tool_calls = None
    mock_resp.usage = None

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_completions = MagicMock()
        mock_completions.create.return_value = mock_resp
        mock_openai_cls.return_value.chat.completions = mock_completions

        client = OpenAIClient()
        client.chat(system="sys", history=[{"role": "user", "content": "go"}])

        _, kwargs = mock_completions.create.call_args
        assert "tools" in kwargs
        assert "response_format" not in kwargs


def test_gemini_chat_with_output_schema_drops_tools_and_sets_mime():
    """chat() drops tools and sets response_schema when output_schema is set."""
    mock_resp = MagicMock()
    mock_resp.candidates[0].content.parts = []
    mock_resp.usage_metadata = None

    fake_config_cls = MagicMock()
    fake_tool_cls = MagicMock()
    fake_models = MagicMock()
    fake_models.generate_content.return_value = mock_resp

    with (
        patch("google.genai.Client") as mock_genai_cls,
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
    ):
        mock_genai_cls.return_value.models = fake_models

        import google.genai.types as gtypes

        with (
            patch.object(gtypes, "GenerateContentConfig", fake_config_cls),
            patch.object(gtypes, "Tool", fake_tool_cls),
        ):
            client = GeminiClient(output_schema=_SAMPLE_SCHEMA)
            client.chat(system="sys", history=[{"role": "user", "parts": [{"text": "go"}]}])

        config_call_kwargs = fake_config_cls.call_args[1]
        assert "tools" not in config_call_kwargs, "tools must be omitted when output_schema is set"
        assert config_call_kwargs.get("response_mime_type") == "application/json"
        assert "response_schema" in config_call_kwargs


def test_gemini_chat_without_output_schema_includes_tools():
    """chat() includes tools and no response_schema when output_schema is None."""
    mock_resp = MagicMock()
    mock_resp.candidates[0].content.parts = []
    mock_resp.usage_metadata = None

    fake_config_cls = MagicMock()
    fake_tool_cls = MagicMock()
    fake_models = MagicMock()
    fake_models.generate_content.return_value = mock_resp

    with (
        patch("google.genai.Client") as mock_genai_cls,
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
    ):
        mock_genai_cls.return_value.models = fake_models

        import google.genai.types as gtypes

        with (
            patch.object(gtypes, "GenerateContentConfig", fake_config_cls),
            patch.object(gtypes, "Tool", fake_tool_cls),
        ):
            client = GeminiClient()
            client.chat(system="sys", history=[{"role": "user", "parts": [{"text": "go"}]}])

        config_call_kwargs = fake_config_cls.call_args[1]
        assert "tools" in config_call_kwargs
        assert "response_schema" not in config_call_kwargs


# ── _resolve_output_schema ────────────────────────────────────────────────────


def test_resolve_output_schema_none_when_absent(tmp_path):
    """Returns None when 'schema' is not in the frontmatter."""
    from uio.core.runner import _resolve_output_schema

    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\n---\nBody.")
    assert _resolve_output_schema({}, str(f)) is None


def test_resolve_output_schema_inline_dict(tmp_path):
    """Returns the inline dict when 'schema' is a mapping."""
    from uio.core.runner import _resolve_output_schema

    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\n---\nBody.")
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    result = _resolve_output_schema({"schema": schema}, str(f))
    assert result == schema


def test_resolve_output_schema_ref_file(tmp_path):
    """Loads and returns the JSON file when 'schema' is a $ref string."""
    import json as _json
    from uio.core.runner import _resolve_output_schema

    schema_file = tmp_path / "output.json"
    schema_data = {"type": "object", "properties": {"result": {"type": "string"}}}
    schema_file.write_text(_json.dumps(schema_data))

    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\n---\nBody.")
    result = _resolve_output_schema({"schema": "output.json"}, str(f))
    assert result == schema_data


def test_resolve_output_schema_dollar_ref_dict(tmp_path):
    """Loads the file when 'schema' is a {'$ref': 'path.json'} mapping."""
    import json as _json
    from uio.core.runner import _resolve_output_schema

    schema_file = tmp_path / "schema.json"
    schema_data = {"type": "object"}
    schema_file.write_text(_json.dumps(schema_data))

    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\n---\nBody.")
    result = _resolve_output_schema({"schema": {"$ref": "schema.json"}}, str(f))
    assert result == schema_data


def test_resolve_output_schema_ref_file_not_found(tmp_path):
    """Raises ValueError when the referenced JSON file does not exist."""
    from uio.core.runner import _resolve_output_schema
    import pytest

    f = tmp_path / "agent.agent.md"
    f.write_text("---\nname: A\ndescription: D.\n---\nBody.")
    with pytest.raises(ValueError, match="not found"):
        _resolve_output_schema({"schema": "missing.json"}, str(f))
