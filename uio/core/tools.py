"""Tool execution."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from uio.core.mcp import MCPClient

MAX_OUTPUT_BYTES = 32768
DEFAULT_TIMEOUT = 300

# Maps --shell choice names to [executable, flag] prefixes for subprocess.run.
_SHELL_MAP: dict[str, list[str]] = {
    "bash": ["bash", "-c"],
    "sh": ["sh", "-c"],
    "zsh": ["zsh", "-c"],
    "powershell": ["powershell.exe", "-Command"],
    "pwsh": ["pwsh", "-Command"],
}

SHELL_CHOICES: list[str] = list(_SHELL_MAP)


def _shell_args(command: str, shell_override: str | None = None) -> tuple:
    """Return (args, shell) for subprocess.run.

    On Windows, shell=True routes to cmd.exe which doesn't understand bash idioms.
    Route to powershell.exe instead so LLM-generated commands work correctly.
    Explicit shell_override (from --shell) always takes precedence.
    """
    if shell_override:
        prefix = _SHELL_MAP.get(shell_override)
        if prefix:
            return prefix + [command], False
    if sys.platform == "win32":
        return ["powershell.exe", "-Command", command], False
    return command, True


TOOL_SCHEMA = {
    "name": "run_command",
    "description": "Execute a shell command and return its stdout and stderr.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."}
        },
        "required": ["command"],
    },
}


class ToolCall(NamedTuple):
    name: str
    args: dict
    call_id: str


def execute_tool(
    tc: ToolCall,
    *,
    mcp_clients: "dict[str, MCPClient] | None" = None,
    timeout: int = DEFAULT_TIMEOUT,
    shell_override: str | None = None,
) -> str:
    if tc.name == "run_command":
        command = tc.args.get("command", "")
        print(f"  [tool] $ {command}")
        try:
            args, use_shell = _shell_args(command, shell_override)
            result = subprocess.run(
                args, shell=use_shell, capture_output=True, text=True, timeout=timeout
            )
            output = result.stdout + result.stderr
            if len(output) > MAX_OUTPUT_BYTES:
                output = "[output truncated]\n" + output[-MAX_OUTPUT_BYTES:]
            print(f"  [tool] exit={result.returncode}")
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return f"[command timed out after {timeout}s]"

    if mcp_clients:
        for server_name, client in mcp_clients.items():
            if tc.name.startswith(f"mcp__{server_name}__"):
                return client.call_tool(tc.name, tc.args)

    return f"Unknown tool: {tc.name}"
