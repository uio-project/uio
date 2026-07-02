"""Structural validation tests for the declarative PM config in .github/.

.github/project.yml and .github/labels.yml are reconciled to GitHub by
scripts/project-sync.sh and the labels-sync workflow. These tests encode the
reconciler's parsing constraints as assertions so config mistakes fail in CI
rather than as duplicate milestones or broken sync runs.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

_GITHUB_DIR = pathlib.Path(__file__).parent.parent / ".github"
_PROJECT_YML = _GITHUB_DIR / "project.yml"
_LABELS_YML = _GITHUB_DIR / "labels.yml"
_LABELS_MD = _GITHUB_DIR / "labels.md"


@pytest.fixture(scope="module")
def project_spec() -> dict:
    return yaml.safe_load(_PROJECT_YML.read_text())


@pytest.fixture(scope="module")
def labels() -> list[dict]:
    return yaml.safe_load(_LABELS_YML.read_text())


# --- project.yml ------------------------------------------------------------


def test_project_spec_has_required_keys(project_spec):
    for key in ("owner", "repo", "issue_types", "milestones", "project"):
        assert key in project_spec, f"project.yml: missing top-level key '{key}'"
    assert project_spec["project"].get("fields"), "project.yml: project.fields is empty"


def test_milestone_titles_are_unique(project_spec):
    # project-sync.sh matches milestones by exact title and never deletes, so a
    # duplicate title in the spec (e.g. after a rename) would create duplicates
    # on GitHub.
    titles = [m["title"] for m in project_spec["milestones"]]
    dupes = {t for t in titles if titles.count(t) > 1}
    assert not dupes, f"project.yml: duplicate milestone titles {dupes}"


def test_milestone_fields_are_single_line(project_spec):
    # project-sync.sh feeds each milestone row through jq @tsv; embedded tabs or
    # newlines in titles/descriptions would corrupt the row parsing.
    for m in project_spec["milestones"]:
        for field in ("title", "description"):
            value = str(m.get(field, ""))
            assert "\n" not in value and "\t" not in value, (
                f"milestone '{m['title']}': {field} must be single-line, tab-free"
            )


def test_milestone_states_are_valid(project_spec):
    for m in project_spec["milestones"]:
        assert m.get("state") in ("open", "closed"), (
            f"milestone '{m['title']}': state must be open or closed"
        )


def test_milestone_due_dates_are_valid(project_spec):
    for m in project_spec["milestones"]:
        due = m.get("due_on")
        if due is None:
            continue
        # PyYAML parses bare dates to datetime.date; project-sync.sh stringifies
        # with default=str, expecting YYYY-MM-DD.
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(due)), (
            f"milestone '{m['title']}': due_on '{due}' is not YYYY-MM-DD"
        )


def test_issue_types_have_name_description_color(project_spec):
    for t in project_spec["issue_types"]:
        for field in ("name", "description", "color"):
            assert t.get(field), f"issue type {t}: missing '{field}'"


# --- labels.yml -------------------------------------------------------------


def test_label_names_are_unique(labels):
    names = [label["name"] for label in labels]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"labels.yml: duplicate label names {dupes}"


def test_label_colors_are_valid_hex(labels):
    for label in labels:
        color = str(label.get("color", ""))
        assert re.fullmatch(r"[0-9a-fA-F]{6}", color), (
            f"label '{label['name']}': color '{color}' is not a 6-digit hex code"
        )


def test_component_labels_are_documented(labels):
    # Every component:* label must appear in the labels.md routing table.
    documented = _LABELS_MD.read_text()
    missing = [
        label["name"]
        for label in labels
        if label["name"].startswith("component:") and f"`{label['name']}`" not in documented
    ]
    assert not missing, f"labels.md: undocumented component labels {missing}"
