"""GitHub App authentication — JWT generation and installation token exchange.

Each GitHub App identity (planner, coder, reviewer) is configured via three
environment variables:

    GITHUB_APP_<ROLE>_ID               — GitHub App's numeric app ID
    GITHUB_APP_<ROLE>_INSTALLATION_ID  — installation ID for the target org/repo
    GITHUB_APP_<ROLE>_PRIVATE_KEY      — PEM-encoded RSA private key (or a path to one)

Where <ROLE> is PLANNER, CODER, or REVIEWER.

Installation tokens are cached in-process and refreshed 60 seconds before expiry
to avoid clock-skew issues.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Final

import jwt

from uio.core.identities import KNOWN_ROLES as KNOWN_ROLES  # re-export for back-compat

# GitHub issues JWTs that expire at most 10 minutes from now.
# Use 9 minutes to leave a safe margin.
_JWT_LIFETIME_SECONDS: Final = 540

# Installation tokens are valid for 1 hour; refresh 60 s before expiry.
_TOKEN_REFRESH_BUFFER_SECONDS: Final = 60


class GitHubAppError(RuntimeError):
    """Raised when GitHub App authentication fails."""


@dataclass
class _CachedToken:
    token: str
    expires_at: float  # Unix timestamp


@dataclass
class GitHubAppClient:
    """Authenticate as a GitHub App and vend short-lived installation tokens.

    Parameters are typically sourced from environment variables via
    ``from_env(role)``, but can be injected directly for testing.
    """

    app_id: str
    private_key_pem: str
    installation_id: str
    _cache: _CachedToken | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls, role: str) -> "GitHubAppClient":
        """Build a client from GITHUB_APP_<ROLE>_* environment variables.

        ``role`` is one of 'planner', 'coder', 'reviewer' (case-insensitive).

        Raises ``GitHubAppError`` if any required variable is absent.
        """
        role_upper = role.upper()
        prefix = f"GITHUB_APP_{role_upper}_"

        app_id = os.environ.get(f"{prefix}ID")
        installation_id = os.environ.get(f"{prefix}INSTALLATION_ID")
        private_key_raw = os.environ.get(f"{prefix}PRIVATE_KEY")

        missing = [
            var
            for var, val in [
                (f"{prefix}ID", app_id),
                (f"{prefix}INSTALLATION_ID", installation_id),
                (f"{prefix}PRIVATE_KEY", private_key_raw),
            ]
            if not val
        ]
        if missing:
            raise GitHubAppError(
                f"GitHub App identity '{role}' is missing environment variables: "
                + ", ".join(missing)
            )

        private_key_pem = _resolve_private_key(private_key_raw)  # type: ignore[arg-type]
        return cls(app_id=app_id, private_key_pem=private_key_pem, installation_id=installation_id)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_installation_token(self) -> str:
        """Return a valid GitHub App installation token, refreshing if needed."""
        now = time.time()
        if self._cache and self._cache.expires_at - now > _TOKEN_REFRESH_BUFFER_SECONDS:
            return self._cache.token

        token, expires_at = self._exchange_token()
        self._cache = _CachedToken(token=token, expires_at=expires_at)
        return token

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_jwt(self) -> str:
        now = int(time.time())
        payload = {
            "iat": now - 60,  # issued-at: 60 s in the past to avoid clock skew
            "exp": now + _JWT_LIFETIME_SECONDS,
            "iss": str(self.app_id),
        }
        return jwt.encode(payload, self.private_key_pem, algorithm="RS256")

    def _exchange_token(self) -> tuple[str, float]:
        """POST to GitHub to exchange the JWT for an installation token."""
        app_jwt = self._make_jwt()
        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        req = urllib.request.Request(
            url,
            method="POST",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "uio-github-app/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise GitHubAppError(
                f"GitHub App token exchange failed (HTTP {exc.code}): {detail}"
            ) from exc
        except OSError as exc:
            raise GitHubAppError(f"GitHub App token exchange network error: {exc}") from exc

        token = body.get("token")
        expires_str = body.get("expires_at", "")
        if not token:
            raise GitHubAppError(f"GitHub App response missing 'token' field: {body}")

        expires_at = _parse_iso8601(expires_str) if expires_str else time.time() + 3600
        return token, expires_at


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _resolve_private_key(raw: str) -> str:
    """Return PEM content from either a literal PEM string or a file path."""
    stripped = raw.strip()
    if stripped.startswith("-----"):
        return stripped
    # Treat as a file path.
    try:
        with open(stripped) as f:
            return f.read().strip()
    except OSError as exc:
        raise GitHubAppError(
            f"GITHUB_APP_*_PRIVATE_KEY looks like a file path but could not be read: {exc}"
        ) from exc


def _parse_iso8601(timestamp: str) -> float:
    """Parse a GitHub ISO-8601 timestamp (e.g. '2026-05-01T12:00:00Z') to Unix time."""
    import datetime

    try:
        dt = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.timestamp()
    except ValueError:
        return time.time() + 3600


def get_token_for_identity(role: str) -> str:
    """Top-level helper: build a GitHubAppClient and return an installation token.

    Raises ``GitHubAppError`` if the identity env vars are missing or the
    token exchange fails.
    """
    client = GitHubAppClient.from_env(role)
    return client.get_installation_token()


def env_vars_present(role: str) -> bool:
    """Return True if all three env vars for *role* are set (non-empty)."""
    role_upper = role.upper()
    prefix = f"GITHUB_APP_{role_upper}_"
    return all(
        os.environ.get(f"{prefix}{suffix}") for suffix in ("ID", "INSTALLATION_ID", "PRIVATE_KEY")
    )
