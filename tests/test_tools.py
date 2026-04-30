"""Tests for tool execution: run_command, truncation, timeout, unknown tools."""


from uio.core.tools import DEFAULT_TIMEOUT, MAX_OUTPUT_BYTES, ToolCall, execute_tool


def call(command: str) -> ToolCall:
    return ToolCall(name="run_command", args={"command": command}, call_id="run_command")


def test_successful_command():
    assert "hello" in execute_tool(call("echo hello"))


def test_nonzero_exit_still_returns_output():
    output = execute_tool(call("echo oops && exit 1"))
    assert "oops" in output


def test_stderr_captured():
    output = execute_tool(call("echo err >&2"))
    assert "err" in output


def test_output_truncated_at_limit():
    big = MAX_OUTPUT_BYTES + 500
    output = execute_tool(call(f"python3 -c \"print('x' * {big})\""))
    assert "[output truncated]" in output
    assert output.startswith("[output truncated]")


def test_tail_biased_truncation_preserves_end():
    sentinel = "SENTINEL_END"
    big = MAX_OUTPUT_BYTES + 1000
    output = execute_tool(call(f"python3 -c \"print('a' * {big}); print('{sentinel}')\""))
    assert "[output truncated]" in output
    assert sentinel in output


def test_output_not_truncated_when_under_limit():
    output = execute_tool(call("echo short"))
    assert "[output truncated]" not in output


def test_empty_output():
    assert execute_tool(call("true")) == "(no output)"


def test_unknown_tool_name():
    tc = ToolCall(name="fly_to_moon", args={}, call_id="fly_to_moon")
    assert "Unknown tool" in execute_tool(tc)


def test_custom_timeout_respected():
    output = execute_tool(call("sleep 5"), timeout=1)
    assert "timed out" in output


def test_timeout_message_includes_seconds():
    output = execute_tool(call("sleep 5"), timeout=1)
    assert "1s" in output


def test_default_timeout_constant():
    assert DEFAULT_TIMEOUT == 300
