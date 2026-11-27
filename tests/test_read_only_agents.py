"""An agent offered only the file tools, and the final turn at the iteration cap."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from uio.core.clients import LLMResponse, TokenUsage
from uio.core.runner import FINAL_TURN_NOTE, _build_preamble, resolve_builtin_tools, run_agent
from uio.core.tools import BUILTIN_TOOLS, ToolCall
from uio.schema.parser import check_unknown_keys, validate_definition


def definition(tmp_path, frontmatter: str) -> dict:
    path = tmp_path / "reader.agent.md"
    path.write_text(
        f"---\nname: reader\ndescription: Reads.\n{frontmatter}---\nRead and report. Stop when done.\n"
    )
    return {
        "agent_name": "reader",
        "definition_path": str(path),
        "no_mcp": True,
        "ledger_path": str(tmp_path / "l.jsonl"),
    }


def looping_client(final_text: str | None):
    """Calls a tool on every turn; on a turn with tools off it answers with ``final_text``."""
    tc = ToolCall(name="read_file", args={"path": "x"}, call_id="t1")
    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]

    def chat(system, history, tools_enabled=True):
        if tools_enabled:
            return LLMResponse(text=None, tool_calls=[tc], usage=TokenUsage(10, 5, 100, 20))
        return LLMResponse(text=final_text, tool_calls=[], usage=TokenUsage(10, 50, 100, 0))

    client.chat.side_effect = chat
    return client


# ── builtin-tools: ─────────────────────────────────────────────────────────────────────


def test_an_agent_is_offered_the_shell_unless_it_names_its_tools():
    assert resolve_builtin_tools({}) == ("run_command",)
    assert resolve_builtin_tools({"builtin-tools": ["read_file", "search_files", "read_file"]}) == (
        "read_file",
        "search_files",
    )
    assert resolve_builtin_tools({"builtin-tools": "list_files"}) == ("list_files",)
    with pytest.raises(ValueError, match="unknown built-in tool"):
        resolve_builtin_tools({"builtin-tools": ["write_file"]})


def test_an_agent_without_the_shell_is_not_told_about_one():
    preamble = _build_preamble(False, builtin=("read_file", "list_files"))
    assert "There is no shell in this run" in preamble and "`read_file`, `list_files`" in preamble
    assert "use `run_command` with the `gh` CLI" not in preamble
    assert "The ONLY tool available is `run_command`" in _build_preamble(False)


def test_only_the_named_tools_reach_the_model_and_run_inside_the_working_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    seen = {}

    def fake_make_client(provider, model, tools=None, **kwargs):
        seen["tools"] = [t["name"] for t in tools]
        client = MagicMock()
        client.build_history.return_value = []
        client.chat.return_value = LLMResponse(text="report", tool_calls=[])
        return client

    with (
        patch("uio.core.runner.make_client", side_effect=fake_make_client),
        patch("uio.core.runner.select_provider_chain", return_value=["anthropic"]),
    ):
        out = run_agent(
            **definition(tmp_path, "builtin-tools: [read_file, list_files, search_files]\n")
        )
    assert out == "report" and seen["tools"] == ["read_file", "list_files", "search_files"]


def test_a_tool_call_gets_the_offered_tools_and_the_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []

    def fake_execute(tc, **kwargs):
        calls.append(kwargs)
        return "contents"

    client = looping_client("done")
    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["anthropic"]),
        patch("uio.core.runner.execute_tool", side_effect=fake_execute),
    ):
        run_agent(
            **definition(tmp_path, "builtin-tools: [read_file]\nguardrails:\n  max_turns: 1\n")
        )
    assert calls[0]["allowed"] == ("read_file",) and calls[0]["fs_root"] == str(tmp_path)


# ── guardrails.final_turn ──────────────────────────────────────────────────────


def test_at_the_cap_a_final_turn_with_tools_off_gives_the_answer(tmp_path):
    client = looping_client("the report from what was read")
    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["anthropic"]),
        patch("uio.core.runner.execute_tool", return_value="ok"),
    ):
        out = run_agent(
            **definition(
                tmp_path,
                "builtin-tools: [read_file]\nguardrails:\n  max_turns: 3\n  final_turn: true\n",
            )
        )
    assert out == "the report from what was read"
    assert client.chat.call_count == 4  # three turns, then the final one
    assert client.chat.call_args.kwargs["tools_enabled"] is False
    client.append_user_text.assert_called_once()
    assert client.append_user_text.call_args.args[1] == FINAL_TURN_NOTE


def test_without_final_turn_the_cap_still_ends_with_no_answer(tmp_path):
    client = looping_client("never asked for")
    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["anthropic"]),
        patch("uio.core.runner.execute_tool", return_value="ok"),
    ):
        out = run_agent(
            **definition(tmp_path, "builtin-tools: [read_file]\nguardrails:\n  max_turns: 2\n")
        )
    assert out is None and client.chat.call_count == 2


def test_a_final_turn_that_still_gives_no_text_ends_with_no_answer(tmp_path):
    client = looping_client(None)
    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["anthropic"]),
        patch("uio.core.runner.execute_tool", return_value="ok"),
    ):
        out = run_agent(**definition(tmp_path, "guardrails:\n  max_turns: 1\n  final_turn: true\n"))
    assert out is None


def test_the_ledger_counts_the_cached_tokens_of_every_turn(tmp_path):
    import json

    client = looping_client("done")
    args = definition(
        tmp_path, "builtin-tools: [read_file]\nguardrails:\n  max_turns: 2\n  final_turn: true\n"
    )
    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["anthropic"]),
        patch("uio.core.runner.execute_tool", return_value="ok"),
    ):
        run_agent(**args)
    entry = json.loads(open(args["ledger_path"]).read().splitlines()[-1])
    assert (entry["prompt_tokens"], entry["completion_tokens"], entry["cache_read_tokens"], entry["cache_write_tokens"]) == (
        30, 60, 300, 40,
    )  # fmt: skip


# ── validation ─────────────────────────────────────────────────────────────────


def test_tools_and_final_turn_are_known_and_checked():
    good = {
        "name": "r",
        "description": "d",
        "builtin-tools": ["read_file"],
        "guardrails": {"final_turn": True},
    }
    assert validate_definition("r.agent.md", good) == []
    assert check_unknown_keys("r.agent.md", good) == []
    bad = {
        "name": "r",
        "description": "d",
        "builtin-tools": ["write_file"],
        "guardrails": {"final_turn": "yes"},
    }
    errors = validate_definition("r.agent.md", bad)
    assert any("unknown built-in tool 'write_file'" in e for e in errors)
    assert any("final_turn' must be true or false" in e for e in errors)
    assert "write_file" not in BUILTIN_TOOLS


def test_an_editors_own_tools_key_is_still_left_alone():
    """`tools: [terminal]` belongs to the editors that share these files: no error, no effect."""
    shared = {"name": "r", "description": "d", "tools": ["terminal"]}
    assert validate_definition("r.agent.md", shared) == []
    assert resolve_builtin_tools(shared) == ("run_command",)
