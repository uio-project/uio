"""uio mcp — generate platform MCP configuration files."""

from __future__ import annotations

import json
import shlex
from pathlib import Path

import click

from uio.config import load_config


def _cmd_parts(raw: str) -> tuple[str, list[str]]:
    parts = shlex.split(raw) if raw else []
    return (parts[0] if parts else ""), (parts[1:] if len(parts) > 1 else [])


def _claude_entry(server_cfg: dict) -> dict:
    command, args = _cmd_parts(server_cfg.get("command", ""))
    entry: dict = {"command": command}
    if args:
        entry["args"] = args
    env_keys = server_cfg.get("env_keys", [])
    if env_keys:
        entry["env"] = {k: f"${{{k}}}" for k in env_keys}
    return entry


def _vscode_entry(server_cfg: dict) -> tuple[dict, list[dict]]:
    command, args = _cmd_parts(server_cfg.get("command", ""))
    entry: dict = {"command": command}
    if args:
        entry["args"] = args
    inputs: list[dict] = []
    env_keys = server_cfg.get("env_keys", [])
    if env_keys:
        env_block: dict = {}
        for k in env_keys:
            input_id = k.lower().replace("_", "-")
            env_block[k] = f"${{input:{input_id}}}"
            inputs.append(
                {
                    "type": "promptString",
                    "id": input_id,
                    "description": k.replace("_", " ").title(),
                    "password": True,
                }
            )
        entry["env"] = env_block
    return entry, inputs


def _write_json(dest: Path, data: dict, force: bool, dry_run: bool) -> None:
    if dest.exists() and not force:
        click.echo(f"  Skipped (exists): {dest}  (use --force to overwrite)")
        return
    content = json.dumps(data, indent=2) + "\n"
    if dry_run:
        click.echo(f"  Would write: {dest}")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        click.echo(f"  Wrote: {dest}")


def _write_claude(mcp_cfg: dict, dest: Path, force: bool, dry_run: bool) -> None:
    output = {"mcpServers": {name: _claude_entry(cfg) for name, cfg in mcp_cfg.items()}}
    _write_json(dest, output, force, dry_run)


def _merge_claude_global(mcp_cfg: dict, settings_path: Path, force: bool, dry_run: bool) -> None:
    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except Exception:
            pass

    servers: dict = existing.get("mcpServers", {})
    changed = False
    for name, server_cfg in mcp_cfg.items():
        if name in servers and not force:
            click.echo(f"  Skipped (exists): mcpServers.{name} in {settings_path}")
            continue
        servers[name] = _claude_entry(server_cfg)
        changed = True
        click.echo(
            f"  {'Would write' if dry_run else 'Wrote'}: mcpServers.{name} → {settings_path}"
        )

    if changed and not dry_run:
        existing["mcpServers"] = servers
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(existing, indent=2) + "\n")


def _write_vscode(mcp_cfg: dict, dest: Path, force: bool, dry_run: bool) -> None:
    all_inputs: list[dict] = []
    all_servers: dict = {}
    for name, server_cfg in mcp_cfg.items():
        entry, inputs = _vscode_entry(server_cfg)
        all_servers[name] = entry
        all_inputs.extend(inputs)

    output: dict = {}
    if all_inputs:
        output["inputs"] = all_inputs
    output["servers"] = all_servers
    _write_json(dest, output, force, dry_run)


@click.group("mcp")
def mcp_group() -> None:
    """Manage MCP server configuration for external tools."""


@mcp_group.command("init")
@click.option(
    "--for",
    "platform",
    type=click.Choice(["claude", "vscode"]),
    required=True,
    help="Target platform: 'claude' writes .mcp.json; 'vscode' writes .vscode/mcp.json.",
)
@click.option(
    "--global",
    "global_",
    is_flag=True,
    default=False,
    help="(claude only) Merge into ~/.claude/settings.json instead of writing .mcp.json.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite the target file if it already exists.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print planned output without writing any files.",
)
def mcp_init_cmd(platform: str, global_: bool, force: bool, dry_run: bool) -> None:
    """Scaffold an MCP config file for Claude Code or VS Code.

    Reads [mcp.<name>] server definitions from uio.toml and writes the
    appropriate config file for the target platform. Secret values are
    never written to disk — env var references are emitted instead.

    Declare env vars required by each server in uio.toml:

    \b
      [mcp.github]
      command  = "github-mcp-server stdio"
      env_keys = ["GITHUB_PERSONAL_ACCESS_TOKEN"]

    \b
    Examples:
      uio mcp init --for claude
      uio mcp init --for vscode
      uio mcp init --for claude --global
      uio mcp init --for claude --force
    """
    if global_ and platform != "claude":
        raise click.UsageError("--global is only supported with --for claude")

    cfg = load_config()
    mcp_cfg = cfg.get("mcp", {})

    if not mcp_cfg:
        raise click.ClickException(
            "No MCP servers configured in uio.toml.\n"
            "Add one or more [mcp.<name>] sections first, for example:\n\n"
            "  [mcp.github]\n"
            '  command  = "github-mcp-server stdio"\n'
            '  env_keys = ["GITHUB_PERSONAL_ACCESS_TOKEN"]'
        )

    if platform == "claude":
        if global_:
            settings_path = Path.home() / ".claude" / "settings.json"
            _merge_claude_global(mcp_cfg, settings_path, force, dry_run)
        else:
            _write_claude(mcp_cfg, Path(".mcp.json"), force, dry_run)
    else:
        _write_vscode(mcp_cfg, Path(".vscode") / "mcp.json", force, dry_run)
