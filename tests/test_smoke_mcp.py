"""Integration smoke tests — spawn real MCP server processes and verify they respond.

Run with:
    pytest -m integration -v

Skipped automatically when required tools (uvx, npx, gh token) are absent.
"""

from __future__ import annotations

import os
import shutil

import pytest

from uio.core.mcp import MCPClient, make_mcp_client


_github_token = (
    os.environ.get("GH_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
)


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("uvx") is None, reason="uvx not on PATH")
def test_git_server_lists_tools(tmp_path):
    """server-git starts, performs JSON-RPC handshake, and lists at least one tool."""
    import subprocess

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    client = MCPClient(
        ["uvx", "mcp-server-git", "--repository", str(tmp_path)],
        server_name="git",
    )
    try:
        tools = client.list_tools()
    finally:
        client.close()

    assert tools, "git MCP server returned no tools"
    tool_names = [t["name"] for t in tools]
    assert any(n.startswith("mcp__git__") for n in tool_names), (
        f"Expected tools prefixed mcp__git__, got: {tool_names}"
    )


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("npx") is None, reason="npx not on PATH")
def test_sequential_thinking_server_lists_tools():
    """sequential-thinking server starts and exposes its sequentialthinking tool."""
    client = MCPClient(
        ["npx", "-y", "@modelcontextprotocol/server-sequential-thinking"],
        server_name="sequential-thinking",
    )
    try:
        tools = client.list_tools()
    finally:
        client.close()

    assert tools, "sequential-thinking MCP server returned no tools"
    tool_names = [t["name"] for t in tools]
    assert any(n.startswith("mcp__sequential-thinking__") for n in tool_names), (
        f"Expected tools prefixed mcp__sequential-thinking__, got: {tool_names}"
    )


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("npx") is None, reason="npx not on PATH")
def test_filesystem_server_lists_tools(tmp_path):
    """filesystem server starts scoped to tmp_path and exposes directory/file tools."""
    client = MCPClient(
        ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(tmp_path)],
        server_name="filesystem",
    )
    try:
        tools = client.list_tools()
    finally:
        client.close()

    assert tools, "filesystem MCP server returned no tools"
    tool_names = [t["name"] for t in tools]
    assert any(n.startswith("mcp__filesystem__") for n in tool_names), (
        f"Expected tools prefixed mcp__filesystem__, got: {tool_names}"
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not (
        os.environ.get("GH_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    ),
    reason="No GitHub token in environment",
)
def test_github_server_lists_tools():
    """GitHub MCP server starts with the available token and lists tools."""
    client = make_mcp_client()
    assert client is not None, "make_mcp_client() returned None despite token being set"
    try:
        tools = client.list_tools()
    finally:
        client.close()

    assert tools, "GitHub MCP server returned no tools"
    tool_names = [t["name"] for t in tools]
    assert any(n.startswith("mcp__github__") for n in tool_names), (
        f"Expected tools prefixed mcp__github__, got: {tool_names}"
    )
