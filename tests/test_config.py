"""Tests for uio.config — load_config defaults and [attribution] block."""

from __future__ import annotations

from uio.config import load_config


def test_load_config_default_attribution_enabled(tmp_path):
    """load_config() returns attribution.enabled = True when no uio.toml exists."""
    cfg = load_config(path=str(tmp_path / "nonexistent.toml"))
    assert cfg["attribution"]["enabled"] is True


def test_load_config_attribution_disabled_via_toml(tmp_path):
    """[attribution] enabled = false in uio.toml is respected."""
    toml_file = tmp_path / "uio.toml"
    toml_file.write_bytes(b"[attribution]\nenabled = false\n")
    cfg = load_config(path=str(toml_file))
    assert cfg["attribution"]["enabled"] is False


def test_load_config_attribution_enabled_explicit_true(tmp_path):
    """[attribution] enabled = true is preserved when explicitly set."""
    toml_file = tmp_path / "uio.toml"
    toml_file.write_bytes(b"[attribution]\nenabled = true\n")
    cfg = load_config(path=str(toml_file))
    assert cfg["attribution"]["enabled"] is True


def test_load_config_attribution_absent_defaults_to_true(tmp_path):
    """When [attribution] is absent from uio.toml the default (True) is used."""
    toml_file = tmp_path / "uio.toml"
    toml_file.write_bytes(b"[runtime]\ntimeout = 60\n")
    cfg = load_config(path=str(toml_file))
    assert cfg["attribution"]["enabled"] is True


def test_load_config_attribution_key_present_in_result(tmp_path):
    """The 'attribution' key is always present in the returned dict."""
    cfg = load_config(path=str(tmp_path / "nonexistent.toml"))
    assert "attribution" in cfg
