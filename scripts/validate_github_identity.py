#!/usr/bin/env python3
"""Validate a uio GitHub App identity after provisioning.

Usage:
    python scripts/validate_github_identity.py <role> [<owner>/<repo>]

    role   — planner, coder, or reviewer
    repo   — optional repository to probe (e.g. uio-project/uio)

The script reads GITHUB_APP_<ROLE>_* environment variables, obtains an
installation token, checks the permissions reported by the token exchange,
and runs a lightweight connectivity probe.

Exit codes:
    0 — all checks passed
    1 — one or more checks failed or env vars are missing
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Required and forbidden permissions per identity (resource: required_level | None = absent).
# None means the permission must NOT appear with write access.
_PERMISSION_POLICY: dict[str, dict[str, str | None]] = {
    "planner": {
        "issues": "write",
        "pull_requests": "write",
        "metadata": "read",
        "contents": None,  # must be absent or read-only
    },
    "coder": {
        "contents": "write",
        "pull_requests": "write",
        "metadata": "read",
        "issues": "read",  # read-only for context; not write
    },
    "reviewer": {
        "pull_requests": "write",
        "issues": "write",
        "metadata": "read",
        "contents": "read",
    },
}

_FORBIDDEN_WRITE: dict[str, list[str]] = {
    "planner": ["contents", "actions", "administration", "secrets"],
    "coder": ["administration", "secrets", "actions"],
    "reviewer": ["contents", "administration", "secrets", "actions"],
}


def _die(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def _warn(msg: str) -> None:
    print(f"  ⚠️  {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")


def _check_env(role: str) -> None:
    role_upper = role.upper()
    prefix = f"GITHUB_APP_{role_upper}_"
    missing = []
    for suffix in ("ID", "INSTALLATION_ID", "PRIVATE_KEY"):
        if not os.environ.get(f"{prefix}{suffix}"):
            missing.append(f"{prefix}{suffix}")
    if missing:
        _die(
            f"Missing environment variables for role '{role}':\n"
            + "\n".join(f"    {v}" for v in missing)
            + "\n\nSet these before running this script. "
            "See docs/provisioning/ for setup instructions."
        )


def _exchange_token(role: str) -> tuple[str, str, dict[str, str]]:
    """Return (token, expires_at, permissions_dict) via the App authentication module."""
    # Import here so the script can report env var problems before the import path is hit.
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        from uio.providers.github.app import GitHubAppClient
    except ImportError:
        _die(
            "Could not import uio.providers.github.app — run from the repo root or install the package."
        )

    client = GitHubAppClient.from_env(role)
    app_jwt = client._make_jwt()

    url = f"https://api.github.com/app/installations/{client.installation_id}/access_tokens"
    req = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "uio-validate-identity/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        _die(f"Token exchange failed (HTTP {exc.code}): {detail}")
    except OSError as exc:
        _die(f"Network error during token exchange: {exc}")

    token = body.get("token", "")
    expires_at = body.get("expires_at", "")
    permissions = body.get("permissions", {})
    return token, expires_at, permissions


def _check_permissions(role: str, permissions: dict[str, str]) -> bool:
    policy = _PERMISSION_POLICY.get(role, {})
    forbidden_write = _FORBIDDEN_WRITE.get(role, [])
    passed = True

    print(f"\n[{role}] Permission check:")
    for resource, required_level in policy.items():
        actual = permissions.get(resource)
        if required_level is None:
            # Must not be write.
            if actual == "write":
                _warn(f"{resource}: got 'write' — must NOT have write access")
                passed = False
            else:
                _ok(f"{resource}: '{actual or 'absent'}' (write not permitted — OK)")
        else:
            if actual == required_level or (
                required_level == "read" and actual in ("read", "write")
            ):
                _ok(f"{resource}: '{actual}' (required: {required_level})")
            else:
                _warn(f"{resource}: got '{actual or 'absent'}' — expected '{required_level}'")
                passed = False

    print(f"\n[{role}] Forbidden write-access check:")
    for resource in forbidden_write:
        actual = permissions.get(resource)
        if actual == "write":
            _warn(f"{resource}: has 'write' access — this identity must NOT have this permission")
            passed = False
        else:
            _ok(f"{resource}: '{actual or 'absent'}' — write access absent")

    return passed


def _connectivity_check(token: str, repo: str | None) -> bool:
    passed = True
    print("\n[connectivity] GET /rate_limit:")
    req = urllib.request.Request(
        "https://api.github.com/rate_limit",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "uio-validate-identity/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            _ok(f"HTTP {resp.status} — token is valid")
    except urllib.error.HTTPError as exc:
        _warn(f"GET /rate_limit returned HTTP {exc.code}")
        passed = False
    except OSError as exc:
        _warn(f"GET /rate_limit network error: {exc}")
        passed = False

    if repo:
        print(f"\n[connectivity] GET /repos/{repo}:")
        req2 = urllib.request.Request(
            f"https://api.github.com/repos/{repo}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "uio-validate-identity/1.0",
            },
        )
        try:
            with urllib.request.urlopen(req2, timeout=10) as resp:
                body = json.loads(resp.read())
                _ok(f"HTTP {resp.status} — repo '{body.get('full_name')}' accessible")
        except urllib.error.HTTPError as exc:
            _warn(f"GET /repos/{repo} returned HTTP {exc.code}")
            passed = False
        except OSError as exc:
            _warn(f"GET /repos/{repo} network error: {exc}")
            passed = False

    return passed


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    role = sys.argv[1].lower()
    repo = sys.argv[2] if len(sys.argv) > 2 else None

    valid_roles = ("planner", "coder", "reviewer")
    if role not in valid_roles:
        _die(f"Unknown role '{role}'. Must be one of: {', '.join(valid_roles)}")

    print(f"[{role}] Checking environment variables...")
    _check_env(role)
    _ok("All required env vars are set")

    print(f"\n[{role}] Authenticating with GitHub App...")
    token, expires_at, permissions = _exchange_token(role)
    _ok(f"Token obtained — expires {expires_at}")

    perms_passed = _check_permissions(role, permissions)
    conn_passed = _connectivity_check(token, repo)

    print()
    if perms_passed and conn_passed:
        print(f"✅ {role.title()} GitHub App identity validated successfully.")
        sys.exit(0)
    else:
        print(
            "❌ Validation failed — review warnings above and check the app's permission\n"
            "   settings at https://github.com/settings/apps",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
