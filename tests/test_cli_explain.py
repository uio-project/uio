"""Tests for uio explain agent/skill/prompt subcommands."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from uio.cli.explain import explain_agent_cmd, explain_group, explain_prompt_cmd, explain_skill_cmd


# ---------------------------------------------------------------------------
# Minimal definition fixtures
# ---------------------------------------------------------------------------

_AGENT_MD = """\
---
name: test-agent
description: A test agent
complexity: small
---

# Agent: test-agent

Your task is to do something useful.
"""

_SKILL_MD = """\
---
name: test-skill
description: A test skill
---

# Skill: test-skill

## Input

Some input.

## Output

Some output.

Your task is to do something useful.
"""

_PROMPT_MD = """\
---
name: test-prompt
description: A test prompt
invokable: true
---

Your task is to do something useful.
"""

_AGENT_WITH_CONTEXT_MD = """\
---
name: ctx-agent
description: An agent with context files
complexity: small
context:
  - "*.md"
---

# Agent: ctx-agent

Your task is to do something with the context.
"""

_AGENT_WITH_IDENTITY_MD = """\
---
name: coder-agent
description: An agent with vcs-identity
complexity: large
vcs-identity: coder
---

# Agent: coder-agent

Your task is to write code.
"""


def _make_cfg(tmp_path, *, extra_dirs=None):
    dirs = {
        "agents": str(tmp_path / "agents"),
        "skills": str(tmp_path / "skills"),
        "prompts": str(tmp_path / "prompts"),
        "workflows": str(tmp_path / "workflows"),
        "memory": str(tmp_path / "memory"),
    }
    if extra_dirs:
        dirs.update(extra_dirs)
    return {
        "dirs": dirs,
        "runtime": {
            "context_max_tokens": 8000,
        },
        "large_agents": {"names": []},
        "attribution": {"enabled": True},
    }


def _write_agent(tmp_path, content=_AGENT_MD, name="test-agent"):
    d = tmp_path / "agents"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.agent.md").write_text(content)


def _write_skill(tmp_path, content=_SKILL_MD, name="test-skill"):
    d = tmp_path / "skills"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.skill.md").write_text(content)


def _write_prompt(tmp_path, content=_PROMPT_MD, name="test-prompt"):
    d = tmp_path / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.prompt.md").write_text(content)


# ---------------------------------------------------------------------------
# explain agent
# ---------------------------------------------------------------------------


class TestExplainAgent:
    def test_annotated_output_contains_markers(self, tmp_path):
        _write_agent(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_agent_cmd, ["test-agent"])

        assert result.exit_code == 0, result.output
        assert "--- preamble ---" in result.output
        assert "--- body ---" in result.output

    def test_annotated_output_contains_body_text(self, tmp_path):
        _write_agent(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_agent_cmd, ["test-agent"])

        assert result.exit_code == 0
        assert "# Agent: test-agent" in result.output
        assert "Your task is to do something useful." in result.output

    def test_raw_flag_strips_markers(self, tmp_path):
        _write_agent(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_agent_cmd, ["test-agent", "--raw"])

        assert result.exit_code == 0
        assert "--- preamble ---" not in result.output
        assert "--- body ---" not in result.output
        # Body content still present
        assert "Your task is to do something useful." in result.output

    def test_raw_output_contains_preamble_text(self, tmp_path):
        _write_agent(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_agent_cmd, ["test-agent", "--raw"])

        assert result.exit_code == 0
        # Preamble content is still present even without the marker
        assert "uio" in result.output

    def test_missing_agent_exits_nonzero(self, tmp_path):
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_agent_cmd, ["no-such-agent"])

        assert result.exit_code != 0

    def test_missing_agent_error_message(self, tmp_path):
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_agent_cmd, ["no-such-agent"])

        assert "no-such-agent" in result.output or "no-such-agent" in (result.exception or "")

    def test_annotated_and_raw_same_content(self, tmp_path):
        """Raw output text must be a subset of the annotated output (minus markers)."""
        _write_agent(tmp_path)
        cfg = _make_cfg(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=cfg):
            annotated = CliRunner().invoke(explain_agent_cmd, ["test-agent"]).output
        with patch("uio.cli.explain.load_config", return_value=cfg):
            raw = CliRunner().invoke(explain_agent_cmd, ["test-agent", "--raw"]).output

        # Every non-marker line in raw output must appear in annotated output
        for line in raw.splitlines():
            assert line in annotated


# ---------------------------------------------------------------------------
# explain skill
# ---------------------------------------------------------------------------


class TestExplainSkill:
    def test_annotated_output_contains_markers(self, tmp_path):
        _write_skill(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_skill_cmd, ["test-skill"])

        assert result.exit_code == 0
        assert "--- preamble ---" in result.output
        assert "--- body ---" in result.output

    def test_annotated_output_contains_body_text(self, tmp_path):
        _write_skill(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_skill_cmd, ["test-skill"])

        assert result.exit_code == 0
        assert "# Skill: test-skill" in result.output

    def test_raw_flag_strips_markers(self, tmp_path):
        _write_skill(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_skill_cmd, ["test-skill", "--raw"])

        assert result.exit_code == 0
        assert "--- preamble ---" not in result.output
        assert "--- body ---" not in result.output

    def test_missing_skill_exits_nonzero(self, tmp_path):
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_skill_cmd, ["no-such-skill"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# explain prompt
# ---------------------------------------------------------------------------


class TestExplainPrompt:
    def test_annotated_output_contains_markers(self, tmp_path):
        _write_prompt(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_prompt_cmd, ["test-prompt"])

        assert result.exit_code == 0
        assert "--- preamble ---" in result.output
        assert "--- body ---" in result.output

    def test_annotated_output_contains_body_text(self, tmp_path):
        _write_prompt(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_prompt_cmd, ["test-prompt"])

        assert result.exit_code == 0
        assert "Your task is to do something useful." in result.output

    def test_prompt_body_has_no_heading_prefix(self, tmp_path):
        """Prompts use the body verbatim — no '# Prompt: ...' heading."""
        _write_prompt(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_prompt_cmd, ["test-prompt"])

        assert result.exit_code == 0
        assert "# Prompt:" not in result.output

    def test_raw_flag_strips_markers(self, tmp_path):
        _write_prompt(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_prompt_cmd, ["test-prompt", "--raw"])

        assert result.exit_code == 0
        assert "--- preamble ---" not in result.output
        assert "--- body ---" not in result.output

    def test_missing_prompt_exits_nonzero(self, tmp_path):
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_prompt_cmd, ["no-such-prompt"])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# context file markers
# ---------------------------------------------------------------------------


class TestExplainContextMarkers:
    def test_context_marker_present(self, tmp_path):
        """When a context glob matches a file, a per-file marker is emitted."""
        d = tmp_path / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ctx-agent.agent.md").write_text(_AGENT_WITH_CONTEXT_MD)

        # Create a file in the cwd that matches "*.md"
        readme = tmp_path / "README.md"
        readme.write_text("# Project README\n\nSome documentation.\n")

        cfg = _make_cfg(tmp_path)
        with (
            patch("uio.cli.explain.load_config", return_value=cfg),
            patch("uio.cli.explain.os.getcwd", return_value=str(tmp_path)),
        ):
            result = CliRunner().invoke(explain_agent_cmd, ["ctx-agent"])

        assert result.exit_code == 0
        # Marker should reference the filename
        assert "--- context:" in result.output
        assert "README.md" in result.output

    def test_context_marker_absent_in_raw(self, tmp_path):
        """Context markers are stripped by --raw."""
        d = tmp_path / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ctx-agent.agent.md").write_text(_AGENT_WITH_CONTEXT_MD)

        readme = tmp_path / "README.md"
        readme.write_text("# Project README\n\nSome documentation.\n")

        cfg = _make_cfg(tmp_path)
        with (
            patch("uio.cli.explain.load_config", return_value=cfg),
            patch("uio.cli.explain.os.getcwd", return_value=str(tmp_path)),
        ):
            result = CliRunner().invoke(explain_agent_cmd, ["ctx-agent", "--raw"])

        assert result.exit_code == 0
        assert "--- context:" not in result.output
        # But the file content should still be present
        assert "Project README" in result.output


# ---------------------------------------------------------------------------
# attribution marker
# ---------------------------------------------------------------------------


class TestExplainAttributionMarker:
    def test_attribution_marker_present_for_vcs_identity_agent(self, tmp_path):
        d = tmp_path / "agents"
        d.mkdir(parents=True, exist_ok=True)
        (d / "coder-agent.agent.md").write_text(_AGENT_WITH_IDENTITY_MD)

        cfg = _make_cfg(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=cfg):
            result = CliRunner().invoke(explain_agent_cmd, ["coder-agent"])

        assert result.exit_code == 0
        assert "--- attribution ---" in result.output

    def test_attribution_marker_absent_for_plain_agent(self, tmp_path):
        _write_agent(tmp_path)
        with patch("uio.cli.explain.load_config", return_value=_make_cfg(tmp_path)):
            result = CliRunner().invoke(explain_agent_cmd, ["test-agent"])

        assert result.exit_code == 0
        assert "--- attribution ---" not in result.output


# ---------------------------------------------------------------------------
# explain group top-level
# ---------------------------------------------------------------------------


class TestExplainGroup:
    def test_no_args_shows_help(self):
        result = CliRunner().invoke(explain_group, ["--help"])
        assert result.exit_code == 0
        assert "agent" in result.output
        assert "skill" in result.output
        assert "prompt" in result.output
