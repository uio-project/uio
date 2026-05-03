"""Tests for transient-error retry logic in runner.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from uio.core.runner import _is_retryable


class TestIsRetryable:
    def test_503_is_retryable(self):
        assert _is_retryable(Exception("HTTP 503 Service Unavailable"))

    def test_429_is_retryable(self):
        assert _is_retryable(Exception("HTTP error 429"))

    def test_unavailable_is_retryable(self):
        assert _is_retryable(Exception("StatusCode.UNAVAILABLE: backend down"))

    def test_too_many_requests_is_retryable(self):
        assert _is_retryable(Exception("Too Many Requests from this IP"))

    def test_rate_limit_is_retryable(self):
        assert _is_retryable(Exception("rate limit exceeded"))

    def test_resource_exhausted_is_retryable(self):
        assert _is_retryable(Exception("RESOURCE_EXHAUSTED: quota exceeded"))

    def test_auth_error_is_not_retryable(self):
        assert not _is_retryable(Exception("401 Unauthorized"))

    def test_bad_request_is_not_retryable(self):
        assert not _is_retryable(Exception("400 Bad Request: invalid model"))


class TestChatRetry:
    """Verify that transient errors are retried before provider fallback fires."""

    def _make_run_args(self, tmp_path):
        """Write a minimal agent definition and return run_agent kwargs."""
        defn = tmp_path / "test.agent.md"
        defn.write_text("---\nname: test-agent\n---\nDo the task.\n")
        return {
            "agent_name": "test-agent",
            "definition_path": str(defn),
            "no_mcp": True,
            "ledger_path": str(tmp_path / "ledger.jsonl"),
        }

    def test_503_retried_then_succeeds(self, tmp_path):
        """client.chat raises 503 twice then returns a terminal response — no provider fallback."""
        from uio.core.clients import LLMResponse
        from uio.core.runner import run_agent

        terminal = LLMResponse(text="Done.", tool_calls=[])
        call_count = {"n": 0}

        def chat_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise Exception("HTTP 503 Service Unavailable")
            return terminal

        mock_client = MagicMock()
        mock_client.build_history.return_value = [{"role": "user", "content": "begin"}]
        mock_client.chat.side_effect = chat_side_effect
        mock_client.usage = None

        with (
            patch("uio.core.runner.make_client", return_value=mock_client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner.time.sleep"),  # don't actually wait
        ):
            run_agent(**self._make_run_args(tmp_path))

        assert call_count["n"] == 3  # two failures + one success

    def test_non_retryable_error_falls_back_immediately(self, tmp_path):
        """A 401 error does not retry — falls straight through to provider fallback."""
        from uio.core.runner import run_agent

        mock_client = MagicMock()
        mock_client.build_history.return_value = [{"role": "user", "content": "begin"}]
        mock_client.chat.side_effect = Exception("401 Unauthorized: bad API key")

        second_client = MagicMock()
        from uio.core.clients import LLMResponse

        second_client.build_history.return_value = [{"role": "user", "content": "begin"}]
        second_client.chat.return_value = LLMResponse(text="Done.", tool_calls=[])
        second_client.usage = None

        clients = iter([mock_client, second_client])

        with (
            patch("uio.core.runner.make_client", side_effect=lambda *a, **kw: next(clients)),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini", "openai"]),
            patch("uio.core.runner.time.sleep"),
        ):
            run_agent(**self._make_run_args(tmp_path))

        # chat was called once on gemini (no retry), then succeeded on openai
        assert mock_client.chat.call_count == 1
        assert second_client.chat.call_count == 1


class TestVcsAliasPreamble:
    """Verify that the VCS alias table is injected based on capabilities, not only vcs-identity."""

    def _make_run_args(self, tmp_path, frontmatter_extra: str = ""):
        defn = tmp_path / "test.agent.md"
        defn.write_text(f"---\nname: test-agent\n{frontmatter_extra}---\nDo the task.\n")
        return {
            "agent_name": "test-agent",
            "definition_path": str(defn),
            "no_mcp": True,
            "ledger_path": str(tmp_path / "ledger.jsonl"),
        }

    def _run_and_capture_system(self, tmp_path, frontmatter_extra: str = "") -> str:
        from uio.core.clients import LLMResponse
        from uio.core.runner import run_agent

        terminal = LLMResponse(text="Done.", tool_calls=[])
        captured: dict[str, str] = {}

        mock_client = MagicMock()
        mock_client.build_history.return_value = [{"role": "user", "content": "begin"}]

        def chat_capture(**kwargs):
            captured["system"] = kwargs.get("system", "")
            return terminal

        mock_client.chat.side_effect = chat_capture
        mock_client.usage = None

        with (
            patch("uio.core.runner.make_client", return_value=mock_client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
        ):
            run_agent(**self._make_run_args(tmp_path, frontmatter_extra))

        return captured.get("system", "")

    def test_capabilities_vcs_injects_alias_table(self, tmp_path):
        """capabilities: [vcs] without vcs-identity should include the VCS alias table."""
        system = self._run_and_capture_system(tmp_path, "capabilities: [vcs]\n")
        assert "VCS Tool Aliases" in system
        assert "vcs__list_issues" in system

    def test_no_vcs_capability_omits_alias_table(self, tmp_path):
        """An agent with neither capabilities nor vcs-identity should not get the alias table."""
        system = self._run_and_capture_system(tmp_path)
        assert "VCS Tool Aliases" not in system

    def test_vcs_identity_still_injects_alias_table(self, tmp_path):
        """vcs-identity path continues to inject the alias table (regression guard)."""
        from uio.core.clients import LLMResponse
        from uio.core.runner import run_agent

        terminal = LLMResponse(text="Done.", tool_calls=[])
        captured: dict[str, str] = {}

        mock_client = MagicMock()
        mock_client.build_history.return_value = [{"role": "user", "content": "begin"}]

        def chat_capture(**kwargs):
            captured["system"] = kwargs.get("system", "")
            return terminal

        mock_client.chat.side_effect = chat_capture

        with (
            patch("uio.core.runner.make_client", return_value=mock_client),
            patch("uio.core.runner.select_provider_chain", return_value=["gemini"]),
            patch("uio.core.runner._inject_vcs_identity", return_value="coder"),
        ):
            run_agent(**self._make_run_args(tmp_path))

        assert "VCS Tool Aliases" in captured.get("system", "")
