"""Tests for tool execution: run_command, truncation, timeout, unknown tools."""

from uio.core.tools import (
    DEFAULT_TIMEOUT,
    MAX_OUTPUT_BYTES,
    SHELL_CHOICES,
    ToolCall,
    _shell_args,
    execute_tool,
)


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


# ── Shell dispatch ────────────────────────────────────────────────────────────


def test_shell_choices_exports_expected_names():
    assert set(SHELL_CHOICES) == {"bash", "sh", "zsh", "powershell", "pwsh"}


def test_shell_args_bash_override():
    args, shell = _shell_args("echo hi", "bash")
    assert args == ["bash", "-c", "echo hi"]
    assert shell is False


def test_shell_args_sh_override():
    args, shell = _shell_args("echo hi", "sh")
    assert args == ["sh", "-c", "echo hi"]
    assert shell is False


def test_shell_args_zsh_override():
    args, shell = _shell_args("echo hi", "zsh")
    assert args == ["zsh", "-c", "echo hi"]
    assert shell is False


def test_shell_args_powershell_override():
    args, shell = _shell_args("echo hi", "powershell")
    assert args == ["powershell.exe", "-Command", "echo hi"]
    assert shell is False


def test_shell_args_pwsh_override():
    args, shell = _shell_args("echo hi", "pwsh")
    assert args == ["pwsh", "-Command", "echo hi"]
    assert shell is False


def test_shell_args_no_override_posix():
    import sys

    if sys.platform != "win32":
        args, shell = _shell_args("echo hi")
        assert args == "echo hi"
        assert shell is True


def test_execute_tool_with_bash_override():
    output = execute_tool(call("echo hello"), shell_override="bash")
    assert "hello" in output


def test_execute_tool_with_sh_override():
    output = execute_tool(call("echo world"), shell_override="sh")
    assert "world" in output


# ── Multi-server MCP dispatch ─────────────────────────────────────────────────


class _FakeMCPClient:
    def __init__(self, server_name: str) -> None:
        self.server_name = server_name
        self.calls: list[tuple[str, dict]] = []

    def call_tool(self, name: str, args: dict) -> str:
        self.calls.append((name, args))
        return f"result from {self.server_name}"

    def close(self) -> None:
        pass


def mcp_tc(name: str) -> ToolCall:
    return ToolCall(name=name, args={}, call_id=name)


def test_mcp_dispatch_routes_to_correct_server():
    gh = _FakeMCPClient("github")
    fs = _FakeMCPClient("filesystem")
    clients = {"github": gh, "filesystem": fs}
    result = execute_tool(mcp_tc("mcp__filesystem__read_file"), mcp_clients=clients)
    assert result == "result from filesystem"
    assert fs.calls == [("mcp__filesystem__read_file", {})]
    assert gh.calls == []


def test_mcp_dispatch_github_server():
    gh = _FakeMCPClient("github")
    clients = {"github": gh}
    result = execute_tool(mcp_tc("mcp__github__list_issues"), mcp_clients=clients)
    assert result == "result from github"
    assert gh.calls == [("mcp__github__list_issues", {})]


def test_mcp_unknown_tool_with_clients_present():
    clients = {"github": _FakeMCPClient("github")}
    result = execute_tool(mcp_tc("mcp__fetch__get"), mcp_clients=clients)
    assert "Unknown tool" in result


def test_mcp_unknown_tool_no_clients():
    result = execute_tool(mcp_tc("mcp__github__search"), mcp_clients=None)
    assert "Unknown tool" in result


def test_mcp_empty_clients_dict():
    result = execute_tool(mcp_tc("mcp__github__search"), mcp_clients={})
    assert "Unknown tool" in result
