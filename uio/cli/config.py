"""uio config subcommands: show, init."""

from __future__ import annotations

import os
from pathlib import Path

import click

from uio.config import get_starter_toml, load_config
from uio.core.clients import PROVIDER_DEFAULTS, PROVIDER_SMALL_MODELS
from uio.core.routing import PROVIDER_KEY_ENV, select_provider_chain


@click.group("config", no_args_is_help=True)
def config_group() -> None:
    """View and initialise project configuration."""


@config_group.command("show")
def config_show_cmd() -> None:
    """Show the resolved provider chain, model defaults, and key settings.

    Example:

    \b
      uio config show
    """
    cfg = load_config()
    chain = select_provider_chain(cfg["runtime"].get("default_provider"))

    click.echo("Provider routing chain:\n")
    all_providers = ["gemini", "openai", "ollama"]
    for provider in all_providers:
        key_env = PROVIDER_KEY_ENV.get(provider)
        if key_env:
            key_set = bool(os.environ.get(key_env))
            status = "✓" if key_set else "✗"
            key_display = f"{key_env}={'***' if key_set else '(not set)'}"
        else:
            status = "✓"
            key_display = "(no key required)"
        chain_note = "  [in routing chain]" if provider in chain else ""
        click.echo(f"  {provider:<8}  {status}  {key_display}{chain_note}")

    click.echo("\nDefault models:\n")
    click.echo(f"  {'PROVIDER':<8}  {'LARGE (default)':<34}  SMALL")
    click.echo(f"  {'--------':<8}  {'---------------':<34}  -----")
    for provider in all_providers:
        large = PROVIDER_DEFAULTS.get(provider, "—")
        small = PROVIDER_SMALL_MODELS.get(provider, "—")
        click.echo(f"  {provider:<8}  {large:<34}  {small}")

    click.echo("\nSettings:\n")
    click.echo(f"  Dirs:         agents={cfg['dirs']['agents']}")
    click.echo(f"                skills={cfg['dirs']['skills']}")
    click.echo(f"                prompts={cfg['dirs']['prompts']}")
    click.echo(f"  Cost ledger:  {cfg['runtime']['cost_ledger']}")
    click.echo(f"  Timeout:      {cfg['runtime']['timeout']}s")
    if cfg["large_agents"]["names"]:
        click.echo(f"  Large agents: {', '.join(cfg['large_agents']['names'])}")
    if os.environ.get("OPENAI_BASE_URL"):
        click.echo(f"  Base URL:     {os.environ['OPENAI_BASE_URL']}")
    if os.environ.get("LLM_MODEL"):
        click.echo(f"  Model (env):  {os.environ['LLM_MODEL']}")


@config_group.command("init")
def config_init_cmd() -> None:
    """Write a starter uio.toml to the current directory.

    Example:

    \b
      uio config init
    """
    dest = Path("uio.toml")
    if dest.exists():
        raise click.ClickException("uio.toml already exists in the current directory.")
    dest.write_text(get_starter_toml())
    click.echo(f"  Created: {dest}")
