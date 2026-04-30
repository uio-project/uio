"""uio registry subcommands: list, search, update, install."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from uio.config import load_config
from uio.registry.manifest import (
    fetch_definition_content,
    fetch_manifest,
    resolve_ref_to_sha,
    search_definitions,
    validate_manifest,
)
from uio.schema.parser import validate_definition, parse_definition_file


@click.group("registry", no_args_is_help=True)
def registry_group() -> None:
    """Discover and install definitions from remote registries.

    Registries are Git repos with a registry.yaml manifest.
    Configure them in uio.toml under [[registries]].

    \b
    Quick start:
      uio registry list
      uio registry search summarise
      uio registry install summarise
    """


@registry_group.command("list")
def registry_list_cmd() -> None:
    """List all configured registries and their status.

    Example:

    \b
      uio registry list
    """
    cfg = load_config()
    registries = cfg.get("registries", [])
    if not registries:
        click.echo(
            "  No registries configured.\n"
            "  Add a [[registries]] entry to uio.toml — run 'uio config show' for an example."
        )
        return

    col_w = [max(len(r.get("name", "")), 8) for r in registries]
    header = f"  {'NAME':<{max(col_w)}}  {'URL':<50}  {'REF':<12}  ENABLED"
    click.echo(header)
    click.echo("  " + "-" * (len(header) - 2))
    for reg in registries:
        name = reg.get("name", "—")
        url = reg.get("url", "—")
        ref = reg.get("ref", "main")
        enabled = "yes" if reg.get("enabled", True) else "no"
        url_display = url if len(url) <= 50 else url[:47] + "..."
        click.echo(f"  {name:<{max(col_w)}}  {url_display:<50}  {ref:<12}  {enabled}")


@registry_group.command("search")
@click.argument("query")
@click.option(
    "--registry", default=None, metavar="NAME", help="Restrict search to a specific registry."
)
def registry_search_cmd(query: str, registry: str | None) -> None:
    """Search for definitions matching QUERY across all enabled registries.

    \b
    Examples:
      uio registry search summarise
      uio registry search code --registry official
    """
    cfg = load_config()
    registries = cfg.get("registries", [])
    if not registries:
        click.echo("  No registries configured. Add [[registries]] entries to uio.toml.")
        return

    if registry:
        registries = [r for r in registries if r.get("name") == registry]
        if not registries:
            raise click.ClickException(f"Registry '{registry}' not found in uio.toml.")

    results = search_definitions(registries, query)
    if not results:
        click.echo(f"  No definitions matching '{query}'.")
        return

    col_name = max(len(r.get("name", "")) for r in results)
    col_type = max(len(r.get("type", "")) for r in results)
    col_reg = max(len(r.get("_registry", "")) for r in results)

    header = f"  {'NAME':<{col_name}}  {'TYPE':<{col_type}}  {'REGISTRY':<{col_reg}}  DESCRIPTION"
    click.echo(header)
    click.echo("  " + "-" * (len(header) - 2))
    for r in results:
        name = r.get("name", "—")
        typ = r.get("type", "—")
        reg = r.get("_registry", "—")
        desc = r.get("description", "—")
        if len(desc) > 60:
            desc = desc[:57] + "..."
        click.echo(f"  {name:<{col_name}}  {typ:<{col_type}}  {reg:<{col_reg}}  {desc}")


@registry_group.command("update")
@click.option("--registry", default=None, metavar="NAME", help="Update only the named registry.")
def registry_update_cmd(registry: str | None) -> None:
    """Refresh all (or one) cached registry manifests.

    Example:

    \b
      uio registry update
    """
    cfg = load_config()
    registries = cfg.get("registries", [])
    if not registries:
        click.echo("  No registries configured.")
        return

    if registry:
        registries = [r for r in registries if r.get("name") == registry]
        if not registries:
            raise click.ClickException(f"Registry '{registry}' not found in uio.toml.")

    errors = 0
    for reg in registries:
        name = reg.get("name", "?")
        try:
            manifest = fetch_manifest(reg, force=True)
            errs = validate_manifest(manifest)
            n = len(manifest.get("definitions", []))
            if errs:
                click.echo(f"  {name}: updated ({n} definitions) — warnings: {'; '.join(errs)}")
            else:
                click.echo(f"  {name}: updated ({n} definitions)")
        except Exception as exc:
            click.echo(f"  {name}: ERROR — {exc}", err=True)
            errors += 1

    if errors:
        sys.exit(1)


@registry_group.command("install")
@click.argument("name")
@click.option(
    "--registry",
    default=None,
    metavar="REGISTRY",
    help="Use only this registry when resolving NAME.",
)
@click.option(
    "--pin",
    is_flag=True,
    default=False,
    help="Resolve the registry ref to a commit SHA and print it.",
)
@click.option(
    "--force", is_flag=True, default=False, help="Overwrite an existing local definition."
)
def registry_install_cmd(name: str, registry: str | None, pin: bool, force: bool) -> None:
    """Install a definition from a registry into .uio/.

    NAME is looked up across all enabled registries (first match wins).
    The installed file is placed in the appropriate .uio/ subdirectory and
    becomes a plain local file with no live dependency on the registry.

    \b
    Examples:
      uio registry install summarise
      uio registry install repo-health --registry official --pin
    """
    cfg = load_config()
    registries = cfg.get("registries", [])
    if not registries:
        raise click.ClickException(
            "No registries configured. Add [[registries]] entries to uio.toml."
        )

    if registry:
        registries = [r for r in registries if r.get("name") == registry]
        if not registries:
            raise click.ClickException(f"Registry '{registry}' not found in uio.toml.")

    # Find the definition entry and its registry
    found_reg: dict | None = None
    found_defn: dict | None = None
    for reg in registries:
        if not reg.get("enabled", True):
            continue
        try:
            manifest = fetch_manifest(reg)
        except Exception:
            continue
        for defn in manifest.get("definitions", []):
            if defn.get("name") == name:
                found_reg = reg
                found_defn = defn
                break
        if found_reg:
            break

    if found_reg is None or found_defn is None:
        raise click.ClickException(
            f"Definition '{name}' not found in any enabled registry. "
            "Run 'uio registry search <query>' to discover available definitions."
        )

    defn_type = found_defn.get("type", "")
    type_to_dir = {
        "agent": cfg["dirs"]["agents"],
        "skill": cfg["dirs"]["skills"],
        "prompt": cfg["dirs"]["prompts"],
    }
    if defn_type not in type_to_dir:
        raise click.ClickException(f"Unknown definition type '{defn_type}' in registry manifest.")

    ext_map = {"agent": ".agent.md", "skill": ".skill.md", "prompt": ".prompt.md"}
    dest_dir = Path(type_to_dir[defn_type])
    dest = dest_dir / f"{name}{ext_map[defn_type]}"

    if dest.exists() and not force:
        raise click.ClickException(f"{dest} already exists. Use --force to overwrite.")

    content = fetch_definition_content(found_reg, found_defn)

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest.write_text(content)
    click.echo(f"  Installed: {dest}  (from registry '{found_reg['name']}')")

    # Post-install validation
    try:
        fm, _ = parse_definition_file(str(dest))
        warnings = validate_definition(str(dest), fm)
        for w in warnings:
            click.echo(f"  Warning: {w}", err=True)
    except Exception as exc:
        click.echo(f"  Warning: could not validate installed file: {exc}", err=True)

    # --pin: resolve branch → SHA and advise the user
    if pin:
        sha = resolve_ref_to_sha(found_reg)
        if sha:
            click.echo(
                f"\n  Pin SHA: {sha}\n"
                f"  To pin, update uio.toml:\n"
                f"    [[registries]]\n"
                f'    name = "{found_reg["name"]}"\n'
                f'    url  = "{found_reg["url"]}"\n'
                f'    ref  = "{sha[:12]}"'
            )
        else:
            click.echo(
                "  --pin: could not resolve ref to SHA "
                "(only GitHub URLs are supported for pinning).",
                err=True,
            )
