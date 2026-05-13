"""Tests for uio.core.attribution — template rendering and system-prompt injection."""

from uio.core.attribution import (
    IDENTITY_DISPLAY_NAMES,
    build_attribution_instructions,
    render_comment_footer,
    render_commit_author,
    render_pr_footer,
)


def test_comment_footer_contains_agent_name():
    footer = render_comment_footer("planner", "github-planner", "0.1.0")
    assert "github-planner" in footer
    assert "(0.1.0)" in footer
    assert "uio" in footer


def test_comment_footer_no_version():
    footer = render_comment_footer("coder", "github-coder")
    assert "github-coder" in footer
    # version_part renders as " ({version})"; absent when omitted
    assert footer.endswith("uio](https://github.com/jomkz/uio)")


def test_comment_footer_starts_with_newlines():
    footer = render_comment_footer("reviewer", "github-reviewer")
    assert footer.startswith("\n\n>")


def test_comment_footer_with_model():
    footer = render_comment_footer("reviewer", "reviewer", "0.1.0", model="claude-sonnet-4-6")
    assert "claude-sonnet-4-6" in footer
    assert "reviewer" in footer
    assert "(0.1.0)" in footer


def test_comment_footer_model_in_parens():
    footer = render_comment_footer("coder", "coder", model="gpt-4o")
    assert "(gpt-4o)" in footer


def test_comment_footer_no_model_no_parens():
    footer = render_comment_footer("planner", "my-planner", "0.1.0")
    # agent_name directly followed by " -", no model parenthetical
    assert "my-planner -" in footer


def test_pr_footer_contains_display_name():
    footer = render_pr_footer("coder")
    assert "AI Coder" in footer
    assert "Human review is required" in footer
    assert "uio" in footer


def test_pr_footer_all_roles():
    for role in ("planner", "coder", "reviewer"):
        footer = render_pr_footer(role)
        assert IDENTITY_DISPLAY_NAMES[role] in footer


def test_render_commit_author_coder():
    author = render_commit_author("coder")
    assert author["name"] == "uio AI Coder"
    assert "uio-coder[bot]" in author["email"]


def test_render_commit_author_returns_copy():
    a = render_commit_author("planner")
    b = render_commit_author("planner")
    a["name"] = "tampered"
    assert b["name"] != "tampered"


def test_build_attribution_instructions_contains_footer():
    block = build_attribution_instructions("planner", "github-planner", "0.1.0")
    assert "AI Planner" in block
    assert "🤖" in block
    assert "uio" in block


def test_build_attribution_instructions_with_model():
    block = build_attribution_instructions("reviewer", "reviewer", "0.1.0", model="claude-opus-4-7")
    assert "claude-opus-4-7" in block


def test_build_attribution_instructions_coder_includes_commit_author():
    block = build_attribution_instructions("coder", "github-coder", "0.1.0")
    assert "user.name" in block
    assert "uio AI Coder" in block
    assert "uio-coder[bot]" in block


def test_build_attribution_instructions_non_coder_no_commit_section():
    for role in ("planner", "reviewer"):
        block = build_attribution_instructions(role, "agent", "0.1.0")
        assert "user.name" not in block


def test_build_attribution_instructions_includes_pr_footer_for_coder():
    block = build_attribution_instructions("coder", "github-coder", "0.1.0")
    assert "AI-generated pull request" in block


def test_build_attribution_instructions_all_roles_valid():
    for role in ("planner", "coder", "reviewer"):
        block = build_attribution_instructions(role, "test-agent")
        assert len(block) > 100
        assert IDENTITY_DISPLAY_NAMES[role] in block


# --- GitLab provider tests ---


def test_render_commit_author_gitlab_email():
    author = render_commit_author("coder", vcs_provider="gitlab")
    assert author["name"] == "uio AI Coder"
    assert "gitlab.com" in author["email"]
    assert "github.com" not in author["email"]


def test_render_commit_author_gitlab_all_roles():
    for role in ("planner", "coder", "reviewer"):
        author = render_commit_author(role, vcs_provider="gitlab")
        assert "gitlab.com" in author["email"]


def test_render_commit_author_github_default():
    author = render_commit_author("coder")
    assert "github.com" in author["email"]


def test_render_commit_author_returns_copy_gitlab():
    a = render_commit_author("coder", vcs_provider="gitlab")
    b = render_commit_author("coder", vcs_provider="gitlab")
    a["email"] = "tampered"
    assert b["email"] != "tampered"


def test_build_attribution_instructions_gitlab_tool_references():
    block = build_attribution_instructions("coder", "gitlab-coder", "0.1.0", vcs_provider="gitlab")
    assert "mcp__gitlab__" in block
    assert "mcp__github__" not in block


def test_build_attribution_instructions_gitlab_mr_terminology():
    block = build_attribution_instructions("planner", "gitlab-planner", vcs_provider="gitlab")
    assert "Merge request" in block or "MR" in block
    assert "Pull request" not in block


def test_build_attribution_instructions_gitlab_identity_label():
    block = build_attribution_instructions("reviewer", "gitlab-reviewer", vcs_provider="gitlab")
    assert "GitLab" in block
    assert "GitHub App" not in block


def test_build_attribution_instructions_gitlab_coder_commit_email():
    block = build_attribution_instructions("coder", "gitlab-coder", vcs_provider="gitlab")
    # The commit author email in the coder commit section must reference gitlab.com.
    assert "uio-coder[bot]@users.noreply.gitlab.com" in block


def test_build_attribution_instructions_github_default_unchanged():
    block = build_attribution_instructions("coder", "github-coder", "0.1.0")
    assert "mcp__github__" in block
    assert "GitHub App" in block


def test_render_pr_footer_gitlab_uses_merge_request():
    footer = render_pr_footer("coder", vcs_provider="gitlab")
    assert "merge request" in footer
    assert "pull request" not in footer


def test_render_pr_footer_github_default_uses_pull_request():
    footer = render_pr_footer("coder")
    assert "pull request" in footer


def test_build_attribution_instructions_gitlab_no_pull_request_language():
    block = build_attribution_instructions("coder", "gitlab-coder", vcs_provider="gitlab")
    assert "pull request" not in block


# --- Unknown role fallback tests (issue #206) ---


def test_render_comment_footer_unknown_role_no_exception():
    footer = render_comment_footer("future-role", "test-agent", "1.0.0")
    assert "test-agent" in footer


def test_render_pr_footer_unknown_role_no_exception():
    footer = render_pr_footer("future-role")
    assert "future-role" in footer


def test_build_attribution_instructions_unknown_role_no_exception():
    block = build_attribution_instructions("future-role", "test-agent", "1.0.0")
    assert "future-role" in block


def test_render_commit_author_unknown_role_no_exception():
    author = render_commit_author("future-role")
    assert author["name"] == "uio future-role"
    assert "future-role" in author["email"]


def test_render_commit_author_unknown_role_gitlab_domain():
    author = render_commit_author("future-role", vcs_provider="gitlab")
    assert "gitlab.com" in author["email"]
    assert "github.com" not in author["email"]


# --- attribution_enabled flag in run_agent ---


def _make_vcs_run_args(tmp_path):
    """Return minimal run_agent kwargs for a vcs-identity (coder) agent."""
    defn = tmp_path / "coder.agent.md"
    defn.write_text("---\nname: github-coder\nvcs-identity: coder\n---\nDo the task.\n")
    return {
        "agent_name": "github-coder",
        "definition_path": str(defn),
        "no_mcp": True,
        "ledger_path": str(tmp_path / "ledger.jsonl"),
    }


def test_attribution_enabled_true_injects_block(tmp_path):
    """When attribution_enabled=True (default), the attribution block is injected for vcs-identity agents."""
    from unittest.mock import MagicMock, patch

    from uio.core.clients import LLMResponse
    from uio.core.runner import run_agent

    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]
    client.chat.return_value = LLMResponse(text="Done.", tool_calls=[])
    client.usage = None

    captured_prompts = []

    def capture_chat(system, history):
        captured_prompts.append(system)
        return LLMResponse(text="Done.", tool_calls=[])

    client.chat.side_effect = capture_chat

    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
        patch("uio.core.runner._inject_vcs_identity", return_value="coder"),
    ):
        run_agent(**_make_vcs_run_args(tmp_path), attribution_enabled=True)

    assert captured_prompts, "chat was never called"
    assert "Attribution" in captured_prompts[0]


def test_attribution_enabled_false_omits_block(tmp_path):
    """When attribution_enabled=False, no attribution block is injected even for vcs-identity agents."""
    from unittest.mock import MagicMock, patch

    from uio.core.clients import LLMResponse
    from uio.core.runner import run_agent

    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]
    client.usage = None

    captured_prompts = []

    def capture_chat(system, history):
        captured_prompts.append(system)
        return LLMResponse(text="Done.", tool_calls=[])

    client.chat.side_effect = capture_chat

    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
        patch("uio.core.runner._inject_vcs_identity", return_value="coder"),
    ):
        run_agent(**_make_vcs_run_args(tmp_path), attribution_enabled=False)

    assert captured_prompts, "chat was never called"
    assert "Attribution" not in captured_prompts[0]


def test_attribution_disabled_with_known_role_omits_block(tmp_path):
    """Guard condition ``role in KNOWN_ROLES and attribution_enabled`` is False when
    attribution_enabled=False, even for a fully-valid vcs-identity role.

    Unlike test_attribution_enabled_false_omits_block this test also asserts that
    the system_prompt still contains the agent body (i.e. only the attribution
    block is absent, not the whole prompt).
    """
    from unittest.mock import MagicMock, patch

    from uio.core.clients import LLMResponse
    from uio.core.identities import KNOWN_ROLES
    from uio.core.runner import run_agent

    assert "coder" in KNOWN_ROLES, "precondition: coder must be a known role"

    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]
    client.usage = None

    captured_prompts = []

    def capture_chat(system, history):
        captured_prompts.append(system)
        return LLMResponse(text="Done.", tool_calls=[])

    client.chat.side_effect = capture_chat

    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
        patch("uio.core.runner._inject_vcs_identity", return_value="coder"),
    ):
        run_agent(**_make_vcs_run_args(tmp_path), attribution_enabled=False)

    assert captured_prompts, "chat was never called"
    system = captured_prompts[0]
    # Attribution block must be absent
    assert "Attribution" not in system
    # But the agent body must still be present
    assert "Do the task." in system


def test_attribution_enabled_default_is_true(tmp_path):
    """attribution_enabled defaults to True — existing behaviour is unchanged."""
    from unittest.mock import MagicMock, patch

    from uio.core.clients import LLMResponse
    from uio.core.runner import run_agent

    client = MagicMock()
    client.build_history.return_value = [{"role": "user", "content": "begin"}]
    client.usage = None

    captured_prompts = []

    def capture_chat(system, history):
        captured_prompts.append(system)
        return LLMResponse(text="Done.", tool_calls=[])

    client.chat.side_effect = capture_chat

    with (
        patch("uio.core.runner.make_client", return_value=client),
        patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
        patch("uio.core.runner._inject_vcs_identity", return_value="coder"),
    ):
        # Do NOT pass attribution_enabled — default should inject attribution
        run_agent(**_make_vcs_run_args(tmp_path))

    assert captured_prompts, "chat was never called"
    assert "Attribution" in captured_prompts[0]
