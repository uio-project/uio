"""Tests for uio.registry.manifest — fetch, cache, search, install, validate."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from uio.cli.registry import registry_install_cmd
from uio.registry.manifest import (
    _raw_url,
    fetch_definition_content,
    fetch_manifest,
    resolve_ref_to_sha,
    search_definitions,
    validate_manifest,
)

# ── Fixtures and helpers ──────────────────────────────────────────────────────

MANIFEST_YAML = """\
version: 1
definitions:
  - name: summarise
    type: skill
    path: skills/summarise.skill.md
    description: Summarise text or a file
    tags: [text, productivity]
  - name: repo-health
    type: agent
    path: agents/repo-health.agent.md
    description: Multi-tool repo health check
    tags: [devops, git]
  - name: ask-docs
    type: prompt
    path: prompts/ask-docs.prompt.md
    description: Ask a question about a codebase
    tags: [docs]
"""

DEFINITION_CONTENT = """\
---
name: summarise
description: Summarise text or a file
---

You are a summariser.
"""

REG = {
    "name": "official",
    "url": "https://github.com/jomkz/uio-registry",
    "ref": "main",
    "enabled": True,
}


def _mock_urlopen(content: str):
    ctx = MagicMock()
    ctx.__enter__ = lambda s: s
    ctx.__exit__ = MagicMock(return_value=False)
    ctx.read.return_value = content.encode()
    return ctx


# ── _raw_url ──────────────────────────────────────────────────────────────────


def test_raw_url_github():
    url = _raw_url("https://github.com/jomkz/uio-registry", "main", "registry.yaml")
    assert url == "https://raw.githubusercontent.com/jomkz/uio-registry/main/registry.yaml"


def test_raw_url_github_trailing_slash():
    url = _raw_url("https://github.com/jomkz/uio-registry/", "v1.0", "skills/x.skill.md")
    assert url == "https://raw.githubusercontent.com/jomkz/uio-registry/v1.0/skills/x.skill.md"


def test_raw_url_gitlab():
    url = _raw_url("https://gitlab.com/myorg/myrepo", "main", "registry.yaml")
    assert url == "https://gitlab.com/myorg/myrepo/-/raw/main/registry.yaml"


def test_raw_url_unknown_host():
    url = _raw_url("https://example.com/my/repo", "main", "registry.yaml")
    assert url == "https://example.com/my/repo/main/registry.yaml"


def test_raw_url_sha_ref():
    sha = "abc1234567890abcdef"
    url = _raw_url("https://github.com/owner/repo", sha, "registry.yaml")
    assert sha in url


# ── fetch_manifest ────────────────────────────────────────────────────────────


def test_fetch_manifest_parses_yaml(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        manifest = fetch_manifest(REG, force=True, cache_dir=tmp_path)
    assert manifest["version"] == 1
    assert len(manifest["definitions"]) == 3


def test_fetch_manifest_caches_to_disk(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        fetch_manifest(REG, force=True, cache_dir=tmp_path)
    assert (tmp_path / "official.yaml").exists()


def test_fetch_manifest_uses_cache_when_fresh(tmp_path):
    (tmp_path / "official.yaml").write_text(MANIFEST_YAML)
    with patch("urllib.request.urlopen") as mock_open:
        fetch_manifest(REG, cache_dir=tmp_path)
    mock_open.assert_not_called()


def test_fetch_manifest_refreshes_stale_cache(tmp_path):
    cache = tmp_path / "official.yaml"
    cache.write_text(MANIFEST_YAML)
    # Make the file appear old
    old_mtime = time.time() - 48 * 3600
    import os

    os.utime(cache, (old_mtime, old_mtime))

    reg_ttl = {**REG, "cache_ttl_hours": 24}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)) as mock_open:
        fetch_manifest(reg_ttl, cache_dir=tmp_path)
    mock_open.assert_called_once()


def test_fetch_manifest_falls_back_to_stale_on_error(tmp_path):
    (tmp_path / "official.yaml").write_text(MANIFEST_YAML)
    old_mtime = time.time() - 48 * 3600
    import os

    os.utime(tmp_path / "official.yaml", (old_mtime, old_mtime))

    reg_ttl = {**REG, "cache_ttl_hours": 24}
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        manifest = fetch_manifest(reg_ttl, cache_dir=tmp_path)
    assert manifest["version"] == 1


def test_fetch_manifest_raises_when_no_cache_and_network_fails(tmp_path):
    with patch("urllib.request.urlopen", side_effect=OSError("network down")):
        with pytest.raises(RuntimeError, match="network down"):
            fetch_manifest(REG, force=True, cache_dir=tmp_path)


def test_fetch_manifest_force_ignores_fresh_cache(tmp_path):
    (tmp_path / "official.yaml").write_text(MANIFEST_YAML)
    updated = (
        MANIFEST_YAML + "  - name: extra\n    type: skill\n    path: x.md\n    description: x\n"
    )
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(updated)):
        manifest = fetch_manifest(REG, force=True, cache_dir=tmp_path)
    assert len(manifest["definitions"]) == 4


# ── search_definitions ────────────────────────────────────────────────────────


def test_search_by_name(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        results = search_definitions([REG], "summarise", cache_dir=tmp_path)
    assert len(results) == 1
    assert results[0]["name"] == "summarise"


def test_search_by_description(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        results = search_definitions([REG], "health", cache_dir=tmp_path)
    assert any(r["name"] == "repo-health" for r in results)


def test_search_by_tag(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        results = search_definitions([REG], "devops", cache_dir=tmp_path)
    assert len(results) == 1
    assert results[0]["name"] == "repo-health"


def test_search_no_results(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        results = search_definitions([REG], "zzznomatch", cache_dir=tmp_path)
    assert results == []


def test_search_injects_registry_name(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        results = search_definitions([REG], "summarise", cache_dir=tmp_path)
    assert results[0]["_registry"] == "official"


def test_search_skips_disabled_registry(tmp_path):
    disabled = {**REG, "enabled": False}
    with patch("urllib.request.urlopen") as mock_open:
        results = search_definitions([disabled], "summarise", cache_dir=tmp_path)
    mock_open.assert_not_called()
    assert results == []


def test_search_continues_on_network_error(tmp_path):
    with patch("urllib.request.urlopen", side_effect=OSError("down")):
        results = search_definitions([REG], "summarise", cache_dir=tmp_path)
    assert results == []


def test_search_across_multiple_registries(tmp_path):
    reg2 = {**REG, "name": "community", "url": "https://github.com/other/uio-reg"}
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        results = search_definitions([REG, reg2], "docs", cache_dir=tmp_path)
    registry_names = {r["_registry"] for r in results}
    assert "official" in registry_names
    assert "community" in registry_names


def test_search_is_case_insensitive(tmp_path):
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MANIFEST_YAML)):
        results = search_definitions([REG], "SUMMARISE", cache_dir=tmp_path)
    assert len(results) == 1


# ── fetch_definition_content ──────────────────────────────────────────────────


def test_fetch_definition_content_returns_text():
    defn = {
        "name": "summarise",
        "type": "skill",
        "path": "skills/summarise.skill.md",
        "description": "x",
    }
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(DEFINITION_CONTENT)):
        content = fetch_definition_content(REG, defn)
    assert "summarise" in content


def test_fetch_definition_content_raises_on_error():
    defn = {
        "name": "summarise",
        "type": "skill",
        "path": "skills/summarise.skill.md",
        "description": "x",
    }
    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        with pytest.raises(RuntimeError, match="timeout"):
            fetch_definition_content(REG, defn)


# ── validate_manifest ─────────────────────────────────────────────────────────


def test_validate_manifest_valid():
    manifest = yaml.safe_load(MANIFEST_YAML)
    assert validate_manifest(manifest) == []


def test_validate_manifest_missing_version():
    manifest = {"definitions": []}
    errors = validate_manifest(manifest)
    assert any("version" in e for e in errors)


def test_validate_manifest_definitions_not_list():
    manifest = {"version": 1, "definitions": "nope"}
    errors = validate_manifest(manifest)
    assert any("list" in e for e in errors)


def test_validate_manifest_missing_required_field():
    manifest = {
        "version": 1,
        "definitions": [{"name": "x", "type": "skill", "path": "x.md"}],
    }
    errors = validate_manifest(manifest)
    assert any("description" in e for e in errors)


def test_validate_manifest_invalid_type():
    manifest = {
        "version": 1,
        "definitions": [{"name": "x", "type": "wizard", "path": "x.md", "description": "d"}],
    }
    errors = validate_manifest(manifest)
    assert any("wizard" in e for e in errors)


def test_validate_manifest_all_valid_types():
    for typ in ("agent", "skill", "prompt"):
        manifest = {
            "version": 1,
            "definitions": [{"name": "x", "type": typ, "path": "x.md", "description": "d"}],
        }
        assert validate_manifest(manifest) == [], f"type '{typ}' should be valid"


# ── resolve_ref_to_sha ────────────────────────────────────────────────────────


def test_resolve_ref_returns_none_for_non_github():
    reg = {"name": "gl", "url": "https://gitlab.com/x/y", "ref": "main"}
    sha = resolve_ref_to_sha(reg)
    assert sha is None


def test_resolve_ref_returns_none_on_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("fail")):
        sha = resolve_ref_to_sha(REG)
    assert sha is None


def test_resolve_ref_parses_sha():
    import json

    fake_resp = MagicMock()
    fake_resp.__enter__ = lambda s: s
    fake_resp.__exit__ = MagicMock(return_value=False)
    fake_resp.read.return_value = json.dumps({"sha": "abc123def456"}).encode()
    with patch("urllib.request.urlopen", return_value=fake_resp):
        sha = resolve_ref_to_sha(REG)
    assert sha == "abc123def456"


# ── registry_install_cmd duplicate warning ────────────────────────────────────

MANIFEST_WITH_SUMMARISE = """\
version: 1
definitions:
  - name: summarise
    type: skill
    path: skills/summarise.skill.md
    description: Summarise text or a file
    tags: [text]
"""


def _make_cfg(tmp_path, registries):
    return {
        "registries": registries,
        "dirs": {
            "agents": str(tmp_path / "agents"),
            "skills": str(tmp_path / "skills"),
            "prompts": str(tmp_path / "prompts"),
        },
        "runtime": {"default_provider": "anthropic", "timeout": 60, "cost_ledger": str(tmp_path / "cost.json")},
        "large_agents": {"names": []},
    }


def test_install_warns_on_duplicate_across_registries(tmp_path):
    """A warning is emitted to stderr when the same name exists in multiple registries."""
    reg1 = {"name": "official", "url": "https://github.com/jomkz/uio-registry", "ref": "main", "enabled": True}
    reg2 = {"name": "community", "url": "https://github.com/other/uio-reg", "ref": "main", "enabled": True}
    cfg = _make_cfg(tmp_path, [reg1, reg2])

    manifest = yaml.safe_load(MANIFEST_WITH_SUMMARISE)

    with (
        patch("uio.cli.registry.load_config", return_value=cfg),
        patch("uio.cli.registry.fetch_manifest", return_value=manifest),
        patch("uio.cli.registry.fetch_definition_content", return_value=DEFINITION_CONTENT),
        patch("uio.cli.registry.parse_definition_file", return_value=({"name": "summarise", "type": "skill"}, "")),
        patch("uio.cli.registry.validate_definition", return_value=[]),
    ):
        result = CliRunner().invoke(registry_install_cmd, ["summarise"])

    assert result.exit_code == 0
    assert "community" in result.output  # warning goes to stderr, mixed into output by CliRunner
    assert "also found" in result.output


def test_install_no_warning_when_no_duplicate(tmp_path):
    """No warning is emitted when the definition exists in only one registry."""
    reg1 = {"name": "official", "url": "https://github.com/jomkz/uio-registry", "ref": "main", "enabled": True}
    reg2_manifest = yaml.safe_load("version: 1\ndefinitions: []\n")
    cfg = _make_cfg(tmp_path, [reg1])

    manifest = yaml.safe_load(MANIFEST_WITH_SUMMARISE)

    with (
        patch("uio.cli.registry.load_config", return_value=cfg),
        patch("uio.cli.registry.fetch_manifest", return_value=manifest),
        patch("uio.cli.registry.fetch_definition_content", return_value=DEFINITION_CONTENT),
        patch("uio.cli.registry.parse_definition_file", return_value=({"name": "summarise", "type": "skill"}, "")),
        patch("uio.cli.registry.validate_definition", return_value=[]),
    ):
        result = CliRunner().invoke(registry_install_cmd, ["summarise"])

    assert result.exit_code == 0
    assert "also found" not in result.output
    _ = reg2_manifest  # unused; kept to clarify intent
