"""MCP stdio client (JSON-RPC 2.0)."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys


class MCPClient:
    """Minimal MCP stdio client for a single server process."""

    def __init__(
        self,
        command: list[str],
        server_name: str = "github",
        env: dict | None = None,
    ) -> None:
        self.server_name = server_name
        self._id = 0
        self._proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env if env is not None else os.environ.copy(),
        )
        self._initialize()

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def _rpc(self, method: str, params: dict) -> dict:
        req_id = self._next_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed connection unexpectedly")
            data = json.loads(line)
            if data.get("id") == req_id:
                if "error" in data:
                    raise RuntimeError(f"MCP error: {data['error']}")
                return data.get("result", {})

    def _notify(self, method: str, params: dict) -> None:
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _initialize(self) -> None:
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "uio", "version": "0.1.0"},
            },
        )
        self._notify("initialized", {})

    def list_tools(self) -> list[dict]:
        """Return tool schemas with names prefixed mcp__<server_name>__."""
        result = self._rpc("tools/list", {})
        tools = []
        for t in result.get("tools", []):
            tools.append(
                {
                    "name": f"mcp__{self.server_name}__{t['name']}",
                    "description": t.get("description", ""),
                    "parameters": t.get("inputSchema", {"type": "object", "properties": {}}),
                }
            )
        return tools

    def call_tool(self, name: str, args: dict) -> str:
        """Call a tool by prefixed name and return text output."""
        prefix = f"mcp__{self.server_name}__"
        actual = name[len(prefix) :] if name.startswith(prefix) else name
        result = self._rpc("tools/call", {"name": actual, "arguments": args})
        parts = [item["text"] for item in result.get("content", []) if item.get("type") == "text"]
        return "\n".join(parts) or "(no output)"

    def close(self) -> None:
        try:
            self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            pass


def _default_github_mcp_command() -> list[str]:
    """Return the best available command to start the GitHub MCP server.

    Probe order:
    1. Standalone binary (github-mcp-server) downloaded from GitHub Releases
    2. Community npm package (@modelcontextprotocol/server-github)
    """
    binary = shutil.which("github-mcp-server")
    if binary:
        return [binary, "stdio"]
    return ["npx", "-y", "@modelcontextprotocol/server-github"]


def make_mcp_client(server_name: str = "github") -> "MCPClient | None":
    """Try to start the GitHub MCP server; return None if no token is available.

    Token priority: GH_TOKEN (set by App identity injection) → GITHUB_TOKEN → GITHUB_PERSONAL_ACCESS_TOKEN.
    The selected token is exported under all three names so that any MCP server implementation
    (gh extension, standalone binary, community npm) can find it regardless of which var it reads.
    """
    token = (
        os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    )
    if not token:
        return None

    command_env = os.environ.copy()
    command_env["GH_TOKEN"] = token
    command_env["GITHUB_TOKEN"] = token
    command_env["GITHUB_PERSONAL_ACCESS_TOKEN"] = token

    using_app_identity = os.environ.get("GH_TOKEN") == token
    if using_app_identity:
        print(f"  [mcp] '{server_name}' starting with App identity token (GH_TOKEN)")
    else:
        print(f"  [mcp] '{server_name}' starting with personal token")

    raw = os.environ.get("MCP_GITHUB_COMMAND")
    command = shlex.split(raw) if raw else _default_github_mcp_command()
    try:
        return MCPClient(command, server_name=server_name, env=command_env)
    except Exception as e:
        hint = (
            "Install the github-mcp-server binary or set "
            "MCP_GITHUB_COMMAND='npx -y @modelcontextprotocol/server-github'."
        )
        print(
            f"  [mcp] Warning: could not start GitHub MCP server: {e}\n  Hint: {hint}",
            file=sys.stderr,
        )
        return None


def make_mcp_clients(
    mcp_cfg: dict,
    plugins: "list[dict] | None" = None,
) -> "dict[str, MCPClient]":
    """Start all MCP servers from config and return a name→client mapping.

    Backwards-compat: if GITHUB_PERSONAL_ACCESS_TOKEN is present and 'github'
    is not in mcp_cfg, the GitHub server is auto-started exactly as before.

    TOML already forbids duplicate keys, but if the same name appears twice in
    a programmatically-constructed dict, the first entry wins (subsequent ones
    are silently skipped so the already-running process is not leaked).

    ``plugins`` is a list of ``[[mcp.plugins]]`` entries from uio.toml.  Each
    entry must have ``name`` and ``command`` fields.  If ``env_keys`` is set,
    all listed environment variables must be present — missing ones cause the
    plugin to be skipped with a warning rather than a hard failure.
    """
    clients: dict[str, MCPClient] = {}

    # Backwards compat: auto-start GitHub when token is set and not in config
    if "github" not in mcp_cfg:
        github_client = make_mcp_client()
        if github_client:
            clients["github"] = github_client

    for name, server_cfg in mcp_cfg.items():
        if name in clients:
            # Already running (github auto-start) or duplicate key — skip.
            continue
        raw_cmd = server_cfg.get("command", "").replace("{cwd}", os.getcwd())
        if not raw_cmd:
            continue
        try:
            clients[name] = MCPClient(shlex.split(raw_cmd), server_name=name)
        except Exception as e:
            print(f"  [mcp] Warning: could not start '{name}' MCP server: {e}", file=sys.stderr)

    for plugin in plugins or []:
        name = plugin.get("name", "")
        if not name:
            continue
        if name in clients:
            print(
                f"  [mcp] Plugin '{name}' skipped — a server with that name is already running.",
                file=sys.stderr,
            )
            continue
        env_keys = plugin.get("env_keys", [])
        missing = [k for k in env_keys if not os.environ.get(k)]
        if missing:
            print(
                f"  [mcp] Warning: plugin '{name}' skipped — missing env vars: "
                + ", ".join(missing),
                file=sys.stderr,
            )
            continue
        raw_cmd = plugin.get("command", "").replace("{cwd}", os.getcwd())
        if not raw_cmd:
            continue
        try:
            clients[name] = MCPClient(shlex.split(raw_cmd), server_name=name)
            print(f"  [mcp] plugin '{name}' started (type={plugin.get('type', '?')})")
        except Exception as e:
            print(f"  [mcp] Warning: could not start plugin '{name}': {e}", file=sys.stderr)

    return clients
