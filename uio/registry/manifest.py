"""Registry manifest fetching, caching, and search.

A registry is a Git repo with a registry.yaml manifest at its root:

    version: 1
    definitions:
      - name: summarise
        type: skill
        path: skills/summarise.skill.md
        description: "Summarise text or a file"
        tags: [text, productivity]

Configured via [[registries]] in uio.toml.  Manifests are cached locally
under ~/.cache/uio/registries/<name>.yaml with a configurable TTL.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "uio" / "registries"
DEFAULT_TTL_HOURS = 24


# ── URL helpers ───────────────────────────────────────────────────────────────

def _raw_url(repo_url: str, ref: str, path: str) -> str:
    """Convert a hosting URL to a raw-content URL for the given ref and path."""
    url = repo_url.rstrip("/")
    if "github.com" in url:
        slug = url.split("github.com/", 1)[1]
        return f"https://raw.githubusercontent.com/{slug}/{ref}/{path}"
    if "gitlab.com" in url:
        slug = url.split("gitlab.com/", 1)[1]
        return f"https://gitlab.com/{slug}/-/raw/{ref}/{path}"
    return f"{url}/{ref}/{path}"


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _fetch_url(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers=_auth_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode()


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(name: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{name}.yaml"


def _is_fresh(path: Path, ttl_hours: int) -> bool:
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < ttl_hours * 3600


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_manifest(
    registry: dict[str, Any],
    *,
    force: bool = False,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Return the parsed manifest dict for a registry.

    Uses the on-disk cache unless *force* is True or the cache is stale.
    On network error, returns the stale cache if available.
    """
    name = registry["name"]
    url = registry["url"]
    ref = registry.get("ref", "main")
    ttl = registry.get("cache_ttl_hours", DEFAULT_TTL_HOURS)
    cdir = cache_dir if cache_dir is not None else DEFAULT_CACHE_DIR
    cache = _cache_path(name, cdir)

    if not force and _is_fresh(cache, ttl):
        return yaml.safe_load(cache.read_text()) or {}

    raw_url = _raw_url(url, ref, "registry.yaml")
    try:
        content = _fetch_url(raw_url)
    except Exception as exc:
        if cache.exists():
            return yaml.safe_load(cache.read_text()) or {}
        raise RuntimeError(
            f"Registry '{name}': failed to fetch manifest from {raw_url}: {exc}"
        ) from exc

    cache.write_text(content)
    return yaml.safe_load(content) or {}


def search_definitions(
    registries: list[dict[str, Any]],
    query: str,
    *,
    cache_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return definitions matching *query* across all enabled registries.

    Each result dict has an extra ``_registry`` key with the registry name.
    """
    q = query.lower()
    results: list[dict[str, Any]] = []
    for reg in registries:
        if not reg.get("enabled", True):
            continue
        try:
            manifest = fetch_manifest(reg, cache_dir=cache_dir)
        except Exception:
            continue
        for defn in manifest.get("definitions", []):
            name = defn.get("name", "")
            desc = defn.get("description", "")
            tags = " ".join(defn.get("tags", []))
            if q in name.lower() or q in desc.lower() or q in tags.lower():
                results.append({**defn, "_registry": reg["name"]})
    return results


def fetch_definition_content(
    registry: dict[str, Any],
    defn: dict[str, Any],
) -> str:
    """Fetch the raw text of a definition file from a registry."""
    url = registry["url"]
    ref = registry.get("ref", "main")
    path = defn["path"]
    raw_url = _raw_url(url, ref, path)
    try:
        return _fetch_url(raw_url)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to fetch '{defn['name']}' from registry '{registry['name']}': {exc}"
        ) from exc


def resolve_ref_to_sha(registry: dict[str, Any]) -> str | None:
    """Resolve the registry's ref to a commit SHA (GitHub only).

    Returns None for non-GitHub URLs or on network errors.
    Used by ``uio registry install --pin`` to produce a pinnable SHA.
    """
    url = registry["url"].rstrip("/")
    ref = registry.get("ref", "main")
    if "github.com" not in url:
        return None
    slug = url.split("github.com/", 1)[1]
    api_url = f"https://api.github.com/repos/{slug}/commits/{ref}"
    headers = {
        "Accept": "application/vnd.github+json",
        **_auth_headers(),
    }
    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("sha")
    except Exception:
        return None


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """Return a list of error strings for a registry manifest. Empty = valid."""
    errors: list[str] = []
    if not isinstance(manifest.get("version"), int):
        errors.append("missing or non-integer 'version' field")
    defs = manifest.get("definitions")
    if not isinstance(defs, list):
        errors.append("'definitions' must be a list")
        return errors
    required = {"name", "type", "path", "description"}
    valid_types = {"agent", "skill", "prompt"}
    for i, defn in enumerate(defs):
        prefix = f"definitions[{i}]"
        for field in required:
            if not defn.get(field):
                errors.append(f"{prefix}: missing required field '{field}'")
        if defn.get("type") and defn["type"] not in valid_types:
            errors.append(
                f"{prefix}: type '{defn['type']}' must be one of {sorted(valid_types)}"
            )
    return errors
