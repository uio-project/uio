"""Tests for uio link — platform integration symlink management."""

from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from uio.cli.link import link_cmd


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_prompts(base: Path, names: list[str]) -> None:
    prompts = base / ".uio" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    for name in names:
        (prompts / f"{name}.prompt.md").write_text(f"# {name}\n")


def _make_agents(base: Path) -> None:
    (base / ".uio" / "agents").mkdir(parents=True, exist_ok=True)


def _make_skills(base: Path) -> None:
    (base / ".uio" / "skills").mkdir(parents=True, exist_ok=True)


def _run(tmp_path: Path, args: list[str], input: str | None = None) -> tuple[int, str]:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # Create a minimal uio.toml using default .uio/ paths
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        result = runner.invoke(link_cmd, args, input=input, catch_exceptions=False)
        return result.exit_code, result.output


# ── idempotency ───────────────────────────────────────────────────────────────


def test_github_links_created(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue", "check-api"])

        result = runner.invoke(link_cmd, ["--platforms", "github"], catch_exceptions=False)
        assert result.exit_code == 0

        assert Path(".github/agents").is_symlink()
        assert Path(".github/prompts").is_symlink()
        assert Path(".github/skills").is_symlink()

        assert os.readlink(".github/agents") == "../.uio/agents"
        assert os.readlink(".github/prompts") == "../.uio/prompts"
        assert os.readlink(".github/skills") == "../.uio/skills"


def test_github_links_idempotent(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue"])

        runner.invoke(link_cmd, ["--platforms", "github"], catch_exceptions=False)
        result = runner.invoke(link_cmd, ["--platforms", "github"], catch_exceptions=False)
        assert result.exit_code == 0
        # second run should produce no Create/Update/Remove lines
        assert "Create" not in result.output
        assert "Update" not in result.output
        assert "Remove" not in result.output


# ── .claude/commands/ per-file symlinks ──────────────────────────────────────


def test_commands_dir_created_with_per_file_symlinks(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue", "check-api-contract"])

        result = runner.invoke(link_cmd, ["--platforms", "claude"], catch_exceptions=False)
        assert result.exit_code == 0

        commands = Path(".claude/commands")
        assert commands.is_dir() and not commands.is_symlink()
        assert (commands / "take-issue.md").is_symlink()
        assert (commands / "check-api-contract.md").is_symlink()
        # .prompt should be stripped from the link name
        assert not (commands / "take-issue.prompt.md").exists()


def test_commands_link_target_is_relative(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["ask-docs"])

        runner.invoke(link_cmd, ["--platforms", "claude"], catch_exceptions=False)

        target = os.readlink(".claude/commands/ask-docs.md")
        assert target == "../../.uio/prompts/ask-docs.prompt.md"


def test_stale_command_link_removed(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue", "old-prompt"])

        runner.invoke(link_cmd, ["--platforms", "claude"], catch_exceptions=False)
        assert Path(".claude/commands/old-prompt.md").exists()

        # Remove the prompt file
        Path(".uio/prompts/old-prompt.prompt.md").unlink()

        result = runner.invoke(link_cmd, ["--platforms", "claude"], catch_exceptions=False)
        assert result.exit_code == 0
        assert not Path(".claude/commands/old-prompt.md").exists()
        assert Path(".claude/commands/take-issue.md").exists()


def test_new_prompt_added_on_rerun(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue"])

        runner.invoke(link_cmd, ["--platforms", "claude"], catch_exceptions=False)

        # Add a new prompt
        Path(".uio/prompts/new-feature.prompt.md").write_text("# new\n")

        runner.invoke(link_cmd, ["--platforms", "claude"], catch_exceptions=False)
        assert Path(".claude/commands/new-feature.md").is_symlink()


# ── directory-symlink migration ──────────────────────────────────────────────


def test_commands_dir_symlink_replaced_with_force(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue"])

        # Simulate legacy setup: .claude/commands is a directory symlink
        Path(".claude").mkdir()
        Path(".claude/commands").symlink_to("../../.uio/prompts")

        result = runner.invoke(
            link_cmd, ["--platforms", "claude", "--force"], catch_exceptions=False
        )
        assert result.exit_code == 0

        commands = Path(".claude/commands")
        assert commands.is_dir() and not commands.is_symlink()
        assert (commands / "take-issue.md").is_symlink()


def test_commands_dir_symlink_kept_when_declined(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue"])

        Path(".claude").mkdir()
        Path(".claude/commands").symlink_to("../../.uio/prompts")

        # User answers "n" to the replacement prompt
        result = runner.invoke(
            link_cmd, ["--platforms", "claude"], input="n\n", catch_exceptions=False
        )
        assert result.exit_code == 0
        assert Path(".claude/commands").is_symlink()


# ── dry-run ───────────────────────────────────────────────────────────────────


def test_dry_run_makes_no_changes(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("uio.toml").write_text(
            "[dirs]\nagents = '.uio/agents'\nskills = '.uio/skills'\nprompts = '.uio/prompts'\n"
        )
        _make_agents(Path("."))
        _make_skills(Path("."))
        _make_prompts(Path("."), ["take-issue"])

        result = runner.invoke(link_cmd, ["--dry-run"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Dry run" in result.output

        assert not Path(".github/agents").exists()
        assert not Path(".claude/agents").exists()
        assert not Path(".claude/commands").exists()


# ── --platforms validation ────────────────────────────────────────────────────


def test_unknown_platform_exits_nonzero(tmp_path):
    exit_code, output = _run(tmp_path, ["--platforms", "bogus"])
    assert exit_code != 0
    assert "Unknown platform" in output
