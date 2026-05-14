"""Tests for uio cost CLI — _load_ledger and _print_cost_table."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from uio.cli.cost import _load_ledger, _print_cost_table, cost_cmd


def _write_ledger(path: Path, entries: list[dict]) -> None:
    with path.open("w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


# --- _load_ledger ---


def test_load_ledger_empty_when_file_missing(tmp_path):
    result = _load_ledger(str(tmp_path / "missing.jsonl"), None, None)
    assert result == []


def test_load_ledger_returns_all_entries(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write_ledger(p, [{"agent": "a"}, {"agent": "b"}])
    entries = _load_ledger(str(p), None, None)
    assert len(entries) == 2


def test_load_ledger_workflow_filter(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write_ledger(
        p,
        [
            {"agent": "a", "workflow": "wf-a"},
            {"agent": "b", "workflow": "wf-b"},
            {"agent": "c", "workflow": "wf-a"},
        ],
    )
    entries = _load_ledger(str(p), None, None, workflow="wf-a")
    assert len(entries) == 2
    assert all(e["workflow"] == "wf-a" for e in entries)


def test_load_ledger_workflow_filter_excludes_no_workflow(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write_ledger(p, [{"agent": "a"}, {"agent": "b", "workflow": "wf"}])
    entries = _load_ledger(str(p), None, None, workflow="wf")
    assert len(entries) == 1
    assert entries[0]["agent"] == "b"


def test_load_ledger_workflow_filter_applied_before_tail(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write_ledger(
        p,
        [{"agent": str(i), "workflow": "wf"} for i in range(10)]
        + [{"agent": "other", "workflow": "other"}],
    )
    entries = _load_ledger(str(p), None, 3, workflow="wf")
    assert len(entries) == 3
    assert all(e["workflow"] == "wf" for e in entries)


def test_load_ledger_tail(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write_ledger(p, [{"agent": str(i)} for i in range(10)])
    entries = _load_ledger(str(p), None, 3)
    assert len(entries) == 3
    assert entries[-1]["agent"] == "9"


# --- _print_cost_table ---


def test_print_cost_table_empty(capsys):
    _print_cost_table([])
    out = capsys.readouterr().out
    assert "(no entries in ledger)" in out


def test_print_cost_table_no_workflow_column_for_plain_entries(capsys):
    _print_cost_table(
        [{"agent": "a", "provider": "x", "model": "m", "total_tokens": 1, "estimated_cost_usd": 0}]
    )
    out = capsys.readouterr().out
    assert "WORKFLOW" not in out


def test_print_cost_table_shows_workflow_column_when_any_entry_has_field(capsys):
    _print_cost_table(
        [
            {
                "agent": "a",
                "workflow": "my-wf",
                "provider": "x",
                "model": "m",
                "total_tokens": 1,
                "estimated_cost_usd": 0,
            }
        ]
    )
    out = capsys.readouterr().out
    assert "WORKFLOW" in out
    assert "my-wf" in out


def test_print_cost_table_total_line(capsys):
    _print_cost_table(
        [
            {"agent": "a", "provider": "x", "model": "m", "total_tokens": 100, "estimated_cost_usd": 0.001},
            {"agent": "b", "provider": "x", "model": "m", "total_tokens": 200, "estimated_cost_usd": 0.002},
        ]
    )
    out = capsys.readouterr().out
    assert "2 run(s)" in out
    assert "300" in out


# --- cost_cmd via CLI runner ---


def test_cost_cmd_workflow_flag_filters(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write_ledger(
        p,
        [
            {"agent": "a", "workflow": "keep", "provider": "x", "model": "m", "total_tokens": 10, "estimated_cost_usd": 0.0},
            {"agent": "b", "workflow": "drop", "provider": "x", "model": "m", "total_tokens": 20, "estimated_cost_usd": 0.0},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(cost_cmd, ["--ledger", str(p), "--workflow", "keep"])
    assert result.exit_code == 0
    assert "keep" in result.output
    assert "drop" not in result.output


def test_cost_cmd_workflow_flag_json(tmp_path):
    p = tmp_path / "ledger.jsonl"
    _write_ledger(
        p,
        [
            {"agent": "a", "workflow": "wf", "total_tokens": 5, "estimated_cost_usd": 0.0},
            {"agent": "b", "total_tokens": 5, "estimated_cost_usd": 0.0},
        ],
    )
    runner = CliRunner()
    result = runner.invoke(cost_cmd, ["--ledger", str(p), "--workflow", "wf", "--json"])
    assert result.exit_code == 0
    lines = [l for l in result.output.strip().splitlines() if l]
    assert len(lines) == 1
    assert json.loads(lines[0])["agent"] == "a"
