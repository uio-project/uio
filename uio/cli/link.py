"""uio link — create and maintain platform integration symlinks."""

from __future__ import annotations

import os
from pathlib import Path

import click

from uio.config import load_config

_PLATFORMS = ("github", "claude")


@click.command("link")
@click.option(
    "--platforms",
    default=None,
    metavar="PLATFORMS",
    help="Comma-separated platforms to link: github,claude. Default: all.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print planned changes without modifying the filesystem.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Replace a .claude/commands directory symlink without prompting.",
)
def link_cmd(platforms: str | None, dry_run: bool, force: bool) -> None:
    """Create and maintain platform integration symlinks.

    Reads source directories from uio.toml (dirs.agents, dirs.skills,
    dirs.prompts) and creates the correct symlinks for each platform.

    For .claude/commands/ the per-file symlinks strip the .prompt infix so
    that Claude Code discovers them as /name rather than /name.prompt.

    \b
    Examples:
      uio link
      uio link --dry-run
      uio link --platforms claude
      uio link --force
    """
    cfg = load_config()
    agents_dir = Path(cfg["dirs"]["agents"])
    skills_dir = Path(cfg["dirs"]["skills"])
    prompts_dir = Path(cfg["dirs"]["prompts"])

    if platforms is not None:
        selected = [p.strip() for p in platforms.split(",")]
        for p in selected:
            if p not in _PLATFORMS:
                raise click.ClickException(
                    f"Unknown platform: {p!r}. Choose from: {', '.join(_PLATFORMS)}"
                )
    else:
        selected = list(_PLATFORMS)

    if dry_run:
        click.echo("Dry run — no changes will be made.\n")

    if "github" in selected:
        _link_github(agents_dir, skills_dir, prompts_dir, dry_run)

    if "claude" in selected:
        _link_claude(agents_dir, skills_dir, prompts_dir, dry_run, force)


def _link_github(agents_dir: Path, skills_dir: Path, prompts_dir: Path, dry_run: bool) -> None:
    github = Path(".github")
    for link, target in [
        (github / "agents", agents_dir),
        (github / "prompts", prompts_dir),
        (github / "skills", skills_dir),
    ]:
        _ensure_symlink(link, target, dry_run)


def _link_claude(
    agents_dir: Path, skills_dir: Path, prompts_dir: Path, dry_run: bool, force: bool
) -> None:
    claude = Path(".claude")
    for link, target in [
        (claude / "agents", agents_dir),
        (claude / "skills", skills_dir),
    ]:
        _ensure_symlink(link, target, dry_run)

    _link_commands(claude / "commands", prompts_dir, dry_run, force)


def _link_commands(commands_dir: Path, prompts_dir: Path, dry_run: bool, force: bool) -> None:
    """Manage per-file symlinks in .claude/commands/ for each *.prompt.md."""
    if commands_dir.is_symlink():
        existing_target = os.readlink(commands_dir)
        click.echo(f"  Detected {commands_dir} is a directory symlink → {existing_target}")
        replace = force or click.confirm(
            "  Replace with a real directory containing per-file symlinks?",
            default=False,
        )
        if not replace:
            click.echo(f"  Skip    {commands_dir}  (kept as directory symlink)")
            return
        click.echo(f"  Remove  {commands_dir}  (directory symlink)")
        if not dry_run:
            commands_dir.unlink()
    elif not commands_dir.exists():
        click.echo(f"  Create  {commands_dir}/")
        if not dry_run:
            commands_dir.mkdir(parents=True, exist_ok=True)

    # Build expected {link_name: prompt_file} from the prompts directory
    expected: dict[str, Path] = {}
    if prompts_dir.exists():
        for prompt_file in sorted(prompts_dir.glob("*.prompt.md")):
            stem = prompt_file.stem  # e.g. "foo.prompt"
            name = stem.removesuffix(".prompt")
            expected[name + ".md"] = prompt_file

    # Remove stale symlinks
    if commands_dir.exists():
        for entry in sorted(commands_dir.iterdir()):
            if entry.is_symlink() and entry.name not in expected:
                click.echo(f"  Remove  {entry}  (stale)")
                if not dry_run:
                    entry.unlink()

    # Create or update per-file symlinks
    for link_name, prompt_file in sorted(expected.items()):
        _ensure_symlink(commands_dir / link_name, prompt_file, dry_run)


def _ensure_symlink(link: Path, target: Path, dry_run: bool) -> None:
    """Create or verify a relative symlink from link to target."""
    rel = Path(os.path.relpath(target, link.parent))

    if link.is_symlink():
        if os.readlink(link) == str(rel):
            return  # already correct
        click.echo(f"  Update  {link}  →  {rel}")
        if not dry_run:
            link.unlink()
            link.symlink_to(rel)
        return

    if link.exists():
        click.echo(f"  Skip    {link}  (exists but is not a symlink)")
        return

    click.echo(f"  Create  {link}  →  {rel}")
    if not dry_run:
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(rel)
