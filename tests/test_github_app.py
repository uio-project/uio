"""Tests for uio/core/github_app.py.

All tests use a locally generated RSA key pair — no real GitHub credentials needed.
The HTTP exchange is exercised via monkeypatching urllib.request.urlopen.
"""

from __future__ import annotations

import json
import os
import time
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from uio.core.github_app import (
    GitHubAppClient,
    GitHubAppError,
    _parse_iso8601,
    _resolve_private_key,
    env_vars_present,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rsa_private_key_pem() -> str:
    """Generate a fresh RSA-2048 key for the test module."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@pytest.fixture
def client(rsa_private_key_pem: str) -> GitHubAppClient:
    return GitHubAppClient(
        app_id="123456",
        private_key_pem=rsa_private_key_pem,
        installation_id="99999",
    )


def _fake_urlopen(token: str = "ghs_faketoken", expires_in: int = 3600):
    """Return a context-manager mock that looks like a GitHub token response."""
    body = json.dumps(
        {
            "token": token,
            "expires_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + expires_in)
            ),
        }
    ).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


# ---------------------------------------------------------------------------
# JWT generation
# ---------------------------------------------------------------------------


def test_make_jwt_returns_string(client: GitHubAppClient) -> None:
    token = client._make_jwt()
    assert isinstance(token, str)
    assert token.count(".") == 2  # header.payload.signature


def test_make_jwt_payload_contains_iss(client: GitHubAppClient) -> None:
    import jwt as pyjwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    priv = load_pem_private_key(client.private_key_pem.encode(), password=None)
    pub_pem = priv.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    raw = client._make_jwt()
    payload = pyjwt.decode(raw, pub_pem, algorithms=["RS256"])
    assert payload["iss"] == client.app_id


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


def test_exchange_token_returns_token_and_expiry(client: GitHubAppClient) -> None:
    mock_resp = _fake_urlopen("ghs_abc123", expires_in=3600)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        token, expires_at = client._exchange_token()
    assert token == "ghs_abc123"
    assert expires_at > time.time()


def test_exchange_token_http_error_raises_github_app_error(client: GitHubAppClient) -> None:
    import urllib.error

    http_err = urllib.error.HTTPError(
        url="https://api.github.com/...",
        code=401,
        msg="Unauthorized",
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(b'{"message":"Bad credentials"}'),
    )
    with patch("urllib.request.urlopen", side_effect=http_err):
        with pytest.raises(GitHubAppError, match="401"):
            client._exchange_token()


def test_exchange_token_network_error_raises_github_app_error(client: GitHubAppClient) -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        with pytest.raises(GitHubAppError, match="network error"):
            client._exchange_token()


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_get_installation_token_is_cached(client: GitHubAppClient) -> None:
    mock_resp = _fake_urlopen("ghs_cached_token", expires_in=3600)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        t1 = client.get_installation_token()
    # Second call must not hit the network.
    with patch("urllib.request.urlopen", side_effect=AssertionError("should not be called")):
        t2 = client.get_installation_token()
    assert t1 == t2 == "ghs_cached_token"


def test_get_installation_token_refreshes_when_near_expiry(
    rsa_private_key_pem: str,
) -> None:
    c = GitHubAppClient(app_id="1", private_key_pem=rsa_private_key_pem, installation_id="2")
    # Seed an almost-expired cache entry (expires in 30 s — within the 60 s buffer).
    from uio.core.github_app import _CachedToken

    c._cache = _CachedToken(token="ghs_old", expires_at=time.time() + 30)

    mock_resp = _fake_urlopen("ghs_new_token", expires_in=3600)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        new_token = c.get_installation_token()
    assert new_token == "ghs_new_token"


# ---------------------------------------------------------------------------
# from_env factory
# ---------------------------------------------------------------------------


def test_from_env_raises_when_vars_missing() -> None:
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_APP_PLANNER_")}
    with patch.dict(os.environ, clean_env, clear=True):
        with pytest.raises(GitHubAppError, match="missing environment variables"):
            GitHubAppClient.from_env("planner")


def test_from_env_builds_client(rsa_private_key_pem: str) -> None:
    extra = {
        "GITHUB_APP_CODER_ID": "42",
        "GITHUB_APP_CODER_INSTALLATION_ID": "100",
        "GITHUB_APP_CODER_PRIVATE_KEY": rsa_private_key_pem,
    }
    with patch.dict(os.environ, extra):
        c = GitHubAppClient.from_env("coder")
    assert c.app_id == "42"
    assert c.installation_id == "100"


# ---------------------------------------------------------------------------
# env_vars_present helper
# ---------------------------------------------------------------------------


def test_env_vars_present_true_when_all_set(rsa_private_key_pem: str) -> None:
    extra = {
        "GITHUB_APP_REVIEWER_ID": "7",
        "GITHUB_APP_REVIEWER_INSTALLATION_ID": "8",
        "GITHUB_APP_REVIEWER_PRIVATE_KEY": rsa_private_key_pem,
    }
    with patch.dict(os.environ, extra):
        assert env_vars_present("reviewer") is True


def test_env_vars_present_false_when_partial() -> None:
    # Build an env that has only REVIEWER_ID, not INSTALLATION_ID or PRIVATE_KEY.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_APP_REVIEWER_")}
    env["GITHUB_APP_REVIEWER_ID"] = "7"
    with patch.dict(os.environ, env, clear=True):
        assert env_vars_present("reviewer") is False


# ---------------------------------------------------------------------------
# _resolve_private_key
# ---------------------------------------------------------------------------


def test_resolve_private_key_returns_literal_pem(rsa_private_key_pem: str) -> None:
    assert _resolve_private_key(rsa_private_key_pem) == rsa_private_key_pem.strip()


def test_resolve_private_key_reads_file(tmp_path, rsa_private_key_pem: str) -> None:
    key_file = tmp_path / "key.pem"
    key_file.write_text(rsa_private_key_pem)
    result = _resolve_private_key(str(key_file))
    assert result == rsa_private_key_pem.strip()


def test_resolve_private_key_bad_path_raises() -> None:
    with pytest.raises(GitHubAppError, match="file path"):
        _resolve_private_key("/nonexistent/path/key.pem")


# ---------------------------------------------------------------------------
# _parse_iso8601
# ---------------------------------------------------------------------------


def test_parse_iso8601_valid() -> None:
    ts = _parse_iso8601("2026-06-01T12:00:00Z")
    assert ts > 0


def test_parse_iso8601_invalid_returns_fallback() -> None:
    before = time.time()
    ts = _parse_iso8601("not-a-date")
    assert ts >= before


# ---------------------------------------------------------------------------
# _inject_vcs_identity — runner integration
# ---------------------------------------------------------------------------


def test_invalid_role_exits(tmp_path, monkeypatch):
    """An unsupported vcs-identity value must produce a hard error at startup."""
    import pytest
    from uio.core.runner import _inject_vcs_identity

    with pytest.raises(SystemExit) as exc_info:
        _inject_vcs_identity({"vcs-identity": "supervillain"})
    assert exc_info.value.code != 0
    assert "supervillain" in str(exc_info.value.code)


def test_no_identity_is_noop(monkeypatch):
    """When neither vcs-identity nor github-identity is set the function is a no-op."""
    from uio.core.runner import _inject_vcs_identity

    original = dict(os.environ)
    result = _inject_vcs_identity({})
    assert result is None
    assert os.environ == original


def test_missing_env_vars_exits(monkeypatch):
    """When vcs-identity is set but env vars are absent, the runner must hard-fail."""
    from uio.core.runner import _inject_vcs_identity

    for var in (
        "GITHUB_APP_CODER_ID",
        "GITHUB_APP_CODER_INSTALLATION_ID",
        "GITHUB_APP_CODER_PRIVATE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(SystemExit) as exc_info:
        _inject_vcs_identity({"vcs-identity": "coder"})
    assert exc_info.value.code != 0
    assert "GITHUB_APP_CODER_" in str(exc_info.value.code)


def test_deprecated_github_identity_still_works(monkeypatch, capsys):
    """Legacy github-identity field is accepted with a deprecation warning."""
    from uio.core.runner import _inject_vcs_identity

    for var in (
        "GITHUB_APP_PLANNER_ID",
        "GITHUB_APP_PLANNER_INSTALLATION_ID",
        "GITHUB_APP_PLANNER_PRIVATE_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    import pytest

    with pytest.raises(SystemExit):
        _inject_vcs_identity({"github-identity": "planner"})
    captured = capsys.readouterr()
    assert "deprecated" in captured.err


def test_invalid_github_identity_role_exits(monkeypatch):
    """An unsupported github-identity value (legacy field) also hard-fails."""
    from uio.core.runner import _inject_vcs_identity
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        _inject_vcs_identity({"github-identity": "wizard"})
    assert exc_info.value.code != 0
