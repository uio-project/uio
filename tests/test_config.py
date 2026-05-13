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


def test_load_config_attribution_enabled_string_false_is_coerced(tmp_path):
    """A string 'false' value for attribution.enabled is coerced to bool False.

    TOML enforces native bool types, so this scenario arises when the value is
    set programmatically (e.g. via environment variable or a non-TOML code path)
    rather than from a real TOML file.  The coercion is tested here via the
    public _coerce_attribution helper used internally by load_config().
    """
    from uio.config import _coerce_attribution

    assert _coerce_attribution({"enabled": "false"})["enabled"] is False
    assert _coerce_attribution({"enabled": "False"})["enabled"] is False
    assert _coerce_attribution({"enabled": "0"})["enabled"] is False
    assert _coerce_attribution({"enabled": "no"})["enabled"] is False
    assert _coerce_attribution({"enabled": ""})["enabled"] is False


def test_load_config_attribution_enabled_string_true_is_coerced(tmp_path):
    """A non-empty non-falsy string value for attribution.enabled is coerced to bool True."""
    from uio.config import _coerce_attribution

    assert _coerce_attribution({"enabled": "true"})["enabled"] is True
    assert _coerce_attribution({"enabled": "True"})["enabled"] is True
    assert _coerce_attribution({"enabled": "1"})["enabled"] is True
    assert _coerce_attribution({"enabled": "yes"})["enabled"] is True
