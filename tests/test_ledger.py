"""Tests for cost ledger: estimation and file append."""

import json
import logging
from pathlib import Path

import uio.core.ledger as ledger_module

from uio.core.ledger import estimate_cost_usd, write_cost_ledger


def test_estimate_gemini_flash_lite():
    cost = estimate_cost_usd("gemini", "gemini-2.5-flash-lite", 1_000_000, 1_000_000)
    assert abs(cost - (0.10 + 0.40)) < 1e-9


def test_estimate_openai_mini():
    cost = estimate_cost_usd("openai", "gpt-4o-mini", 1_000_000, 1_000_000)
    assert abs(cost - (0.15 + 0.60)) < 1e-9


def test_estimate_unknown_provider(monkeypatch, caplog):
    monkeypatch.setattr(ledger_module, "_warned_unknown_models", set())
    with caplog.at_level(logging.WARNING, logger="uio.core.ledger"):
        cost = estimate_cost_usd("unknown", "unknown-model", 1_000_000, 1_000_000)
    assert cost == 0.0
    assert any("unknown/unknown-model" in r.message for r in caplog.records)


def test_estimate_unknown_model_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(ledger_module, "_warned_unknown_models", set())
    with caplog.at_level(logging.WARNING, logger="uio.core.ledger"):
        estimate_cost_usd("acme", "acme-turbo", 1_000, 500)
    assert any("acme/acme-turbo" in r.message for r in caplog.records)


def test_estimate_unknown_model_warns_once(monkeypatch, caplog):
    monkeypatch.setattr(ledger_module, "_warned_unknown_models", set())
    with caplog.at_level(logging.WARNING, logger="uio.core.ledger"):
        estimate_cost_usd("acme2", "acme2-turbo", 1_000, 500)
        estimate_cost_usd("acme2", "acme2-turbo", 2_000, 1_000)
    matching = [r for r in caplog.records if "acme2/acme2-turbo" in r.message]
    assert len(matching) == 1


def test_write_creates_file(tmp_path):
    ledger = str(tmp_path / "test_cost.jsonl")
    write_cost_ledger("test-agent", "gemini", "gemini-2.5-flash", 100, 50, ledger)
    assert Path(ledger).exists()


def test_write_appends_valid_json(tmp_path):
    ledger = str(tmp_path / "test_cost.jsonl")
    write_cost_ledger("agent-a", "gemini", "gemini-2.5-flash", 100, 50, ledger)
    write_cost_ledger("agent-b", "openai", "gpt-4o", 200, 100, ledger)
    lines = Path(ledger).read_text().strip().splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert entry["agent"] == "agent-a"
    assert entry["provider"] == "gemini"
    assert entry["total_tokens"] == 150
    assert "estimated_cost_usd" in entry
    assert "timestamp" in entry


def test_write_cost_is_nonzero_for_paid_provider(tmp_path):
    ledger = str(tmp_path / "cost.jsonl")
    write_cost_ledger("my-agent", "openai", "gpt-4o", 1_000_000, 1_000_000, ledger)
    entry = json.loads(Path(ledger).read_text().strip())
    assert entry["estimated_cost_usd"] > 0


def test_write_cost_is_zero_for_ollama(tmp_path):
    ledger = str(tmp_path / "cost.jsonl")
    write_cost_ledger("my-agent", "ollama", "qwen2.5-coder:32b", 100_000, 50_000, ledger)
    entry = json.loads(Path(ledger).read_text().strip())
    assert entry["estimated_cost_usd"] == 0.0
