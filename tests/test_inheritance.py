"""Tests for the extends: frontmatter inheritance feature."""

from __future__ import annotations

import textwrap

import pytest

from uio.schema.parser import (
    check_inheritance_cycles,
    parse_definition_file,
    resolve_inheritance,
    validate_definition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(tmp_path, filename: str, content: str):
    """Write *content* to *tmp_path/filename* and return the path string."""
    f = tmp_path / filename
    f.write_text(textwrap.dedent(content))
    return str(f)


# ---------------------------------------------------------------------------
# validate_definition: extends: is a known key
# ---------------------------------------------------------------------------


def test_validate_extends_field_accepted(tmp_path):
    """'extends:' must not produce an 'unrecognised key' error."""
    f = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: A child agent.
        extends: base
        ---
        Child body.
        """,
    )
    fm, _ = parse_definition_file(f)
    errors = validate_definition(f, fm)
    assert not any("extends" in e for e in errors)


# ---------------------------------------------------------------------------
# resolve_inheritance: basic single-level inheritance
# ---------------------------------------------------------------------------


def test_basic_inheritance_appends_body(tmp_path):
    """Child body is appended after parent body by default."""
    _write(
        tmp_path,
        "base.agent.md",
        """\
        ---
        name: Base
        description: The base agent.
        ---
        Parent body.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: The child agent.
        extends: base
        ---
        Child body.
        """,
    )
    fm, body = parse_definition_file(child_path)
    merged_fm, merged_body = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])

    assert "Parent body." in merged_body
    assert "Child body." in merged_body
    # Parent comes first
    assert merged_body.index("Parent body.") < merged_body.index("Child body.")


def test_basic_inheritance_merges_frontmatter(tmp_path):
    """Child frontmatter overrides parent; shared keys use child values."""
    _write(
        tmp_path,
        "base.agent.md",
        """\
        ---
        name: Base
        description: The base agent.
        complexity: small
        tools:
          - terminal
        ---
        Parent body.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: The child agent.
        extends: base
        complexity: large
        ---
        Child body.
        """,
    )
    fm, body = parse_definition_file(child_path)
    merged_fm, _ = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])

    # Child identity fields are preserved
    assert merged_fm["name"] == "Child"
    assert merged_fm["description"] == "The child agent."
    # Child overrides complexity
    assert merged_fm["complexity"] == "large"
    # Inherited from parent
    assert merged_fm["tools"] == ["terminal"]
    # extends: key itself is not in the merged frontmatter
    assert "extends" not in merged_fm


def test_child_name_and_description_always_from_child(tmp_path):
    """name and description are never inherited from the parent."""
    _write(
        tmp_path,
        "base.agent.md",
        """\
        ---
        name: Base Name
        description: Base description.
        ---
        Body.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child Name
        description: Child description.
        extends: base
        ---
        Child.
        """,
    )
    fm, body = parse_definition_file(child_path)
    merged_fm, _ = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])

    assert merged_fm["name"] == "Child Name"
    assert merged_fm["description"] == "Child description."


# ---------------------------------------------------------------------------
# resolve_inheritance: # Override marker
# ---------------------------------------------------------------------------


def test_override_marker_replaces_parent_body(tmp_path):
    """A child body starting with '# Override' replaces the parent body entirely."""
    _write(
        tmp_path,
        "base.agent.md",
        """\
        ---
        name: Base
        description: Base.
        ---
        Parent body that should not appear.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: Child.
        extends: base
        ---
        # Override
        Completely new body.
        """,
    )
    fm, body = parse_definition_file(child_path)
    merged_fm, merged_body = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])

    assert "Parent body" not in merged_body
    assert "Completely new body." in merged_body
    # The marker line itself is stripped
    assert "# Override" not in merged_body


def test_override_marker_content_is_preserved(tmp_path):
    """Everything after '# Override\\n' in the child body is the replacement content."""
    _write(
        tmp_path,
        "base.agent.md",
        """\
        ---
        name: Base
        description: Base.
        ---
        Original.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: Child.
        extends: base
        ---
        # Override
        Line one.
        Line two.
        """,
    )
    fm, body = parse_definition_file(child_path)
    _, merged_body = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])

    assert "Line one." in merged_body
    assert "Line two." in merged_body


# ---------------------------------------------------------------------------
# resolve_inheritance: multi-level chains
# ---------------------------------------------------------------------------


def test_multi_level_chain(tmp_path):
    """A -> B -> C: grandparent body comes first, then parent's, then child's."""
    _write(
        tmp_path,
        "grandparent.agent.md",
        """\
        ---
        name: Grandparent
        description: Grandparent.
        ---
        Grandparent body.
        """,
    )
    _write(
        tmp_path,
        "parent.agent.md",
        """\
        ---
        name: Parent
        description: Parent.
        extends: grandparent
        ---
        Parent body.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: Child.
        extends: parent
        ---
        Child body.
        """,
    )
    fm, body = parse_definition_file(child_path)
    _, merged_body = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])

    assert "Grandparent body." in merged_body
    assert "Parent body." in merged_body
    assert "Child body." in merged_body
    # Order: grandparent first, then parent, then child
    gp_pos = merged_body.index("Grandparent body.")
    p_pos = merged_body.index("Parent body.")
    c_pos = merged_body.index("Child body.")
    assert gp_pos < p_pos < c_pos


def test_multi_level_frontmatter_merge(tmp_path):
    """Frontmatter merges correctly across a three-level chain."""
    _write(
        tmp_path,
        "grandparent.agent.md",
        """\
        ---
        name: Grandparent
        description: Grandparent.
        complexity: small
        tools:
          - terminal
        ---
        GP body.
        """,
    )
    _write(
        tmp_path,
        "parent.agent.md",
        """\
        ---
        name: Parent
        description: Parent.
        extends: grandparent
        complexity: large
        ---
        Parent body.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: Child.
        extends: parent
        ---
        Child body.
        """,
    )
    fm, body = parse_definition_file(child_path)
    merged_fm, _ = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])

    # Grandparent's tools inherited through parent
    assert merged_fm["tools"] == ["terminal"]
    # Parent overrode complexity to large; child does not override it
    assert merged_fm["complexity"] == "large"
    assert merged_fm["name"] == "Child"


# ---------------------------------------------------------------------------
# resolve_inheritance: error cases
# ---------------------------------------------------------------------------


def test_missing_parent_raises_file_not_found(tmp_path):
    """Resolving a definition that extends a non-existent parent raises FileNotFoundError."""
    child_path = _write(
        tmp_path,
        "orphan.agent.md",
        """\
        ---
        name: Orphan
        description: Orphan.
        extends: does-not-exist
        ---
        Body.
        """,
    )
    fm, body = parse_definition_file(child_path)
    with pytest.raises(FileNotFoundError, match="does-not-exist"):
        resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])


def test_no_extends_returns_unchanged(tmp_path):
    """A definition without 'extends:' is returned unchanged."""
    path = _write(
        tmp_path,
        "plain.agent.md",
        """\
        ---
        name: Plain
        description: Plain.
        ---
        Plain body.
        """,
    )
    fm, body = parse_definition_file(path)
    merged_fm, merged_body = resolve_inheritance(path, fm, body, search_dirs=[str(tmp_path)])
    assert merged_fm == fm
    assert merged_body == body


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def test_direct_cycle_raises(tmp_path):
    """A extends B, B extends A → cycle is detected and raises ValueError."""
    a_path = _write(
        tmp_path,
        "a.agent.md",
        """\
        ---
        name: A
        description: A.
        extends: b
        ---
        A body.
        """,
    )
    _write(
        tmp_path,
        "b.agent.md",
        """\
        ---
        name: B
        description: B.
        extends: a
        ---
        B body.
        """,
    )
    fm, body = parse_definition_file(a_path)
    with pytest.raises(ValueError, match="cycle"):
        resolve_inheritance(a_path, fm, body, search_dirs=[str(tmp_path)])


def test_indirect_cycle_raises(tmp_path):
    """A extends B, B extends C, C extends A → cycle is detected."""
    a_path = _write(
        tmp_path,
        "a.agent.md",
        """\
        ---
        name: A
        description: A.
        extends: b
        ---
        A body.
        """,
    )
    _write(
        tmp_path,
        "b.agent.md",
        """\
        ---
        name: B
        description: B.
        extends: c
        ---
        B body.
        """,
    )
    _write(
        tmp_path,
        "c.agent.md",
        """\
        ---
        name: C
        description: C.
        extends: a
        ---
        C body.
        """,
    )
    fm, body = parse_definition_file(a_path)
    with pytest.raises(ValueError, match="cycle"):
        resolve_inheritance(a_path, fm, body, search_dirs=[str(tmp_path)])


def test_check_inheritance_cycles_detects_cycle(tmp_path):
    """check_inheritance_cycles returns a warning when a cycle exists."""
    a_path = _write(
        tmp_path,
        "a.agent.md",
        """\
        ---
        name: A
        description: A.
        extends: b
        ---
        A body.
        """,
    )
    _write(
        tmp_path,
        "b.agent.md",
        """\
        ---
        name: B
        description: B.
        extends: a
        ---
        B body.
        """,
    )
    warnings = check_inheritance_cycles([a_path])
    assert len(warnings) >= 1
    assert any("cycle" in w.lower() for w in warnings)


def test_check_inheritance_cycles_no_cycle(tmp_path):
    """check_inheritance_cycles returns no warnings when chains are valid."""
    _write(
        tmp_path,
        "base.agent.md",
        """\
        ---
        name: Base
        description: Base.
        ---
        Base body.
        """,
    )
    child_path = _write(
        tmp_path,
        "child.agent.md",
        """\
        ---
        name: Child
        description: Child.
        extends: base
        ---
        Child body.
        """,
    )
    warnings = check_inheritance_cycles([child_path])
    assert warnings == []


def test_check_inheritance_cycles_missing_parent_warns(tmp_path):
    """check_inheritance_cycles warns when the parent definition does not exist."""
    child_path = _write(
        tmp_path,
        "orphan.agent.md",
        """\
        ---
        name: Orphan
        description: Orphan.
        extends: nonexistent
        ---
        Body.
        """,
    )
    warnings = check_inheritance_cycles([child_path])
    assert len(warnings) >= 1
    assert any("nonexistent" in w for w in warnings)


def test_check_inheritance_cycles_skips_no_extends(tmp_path):
    """check_inheritance_cycles is silent for definitions without extends:."""
    plain_path = _write(
        tmp_path,
        "plain.agent.md",
        """\
        ---
        name: Plain
        description: Plain.
        ---
        Plain body.
        """,
    )
    warnings = check_inheritance_cycles([plain_path])
    assert warnings == []


# ---------------------------------------------------------------------------
# Skill file resolution via extends
# ---------------------------------------------------------------------------


def test_extends_resolves_skill_file(tmp_path):
    """extends: can refer to a .skill.md parent."""
    _write(
        tmp_path,
        "base-skill.skill.md",
        """\
        ---
        name: base-skill
        description: Base skill.
        ---
        ## Input
        Base skill body.

        ## Output
        Result.
        """,
    )
    child_path = _write(
        tmp_path,
        "child-skill.skill.md",
        """\
        ---
        name: child-skill
        description: Child skill.
        extends: base-skill
        ---
        Extra child instructions.
        """,
    )
    fm, body = parse_definition_file(child_path)
    merged_fm, merged_body = resolve_inheritance(child_path, fm, body, search_dirs=[str(tmp_path)])
    assert "Base skill body." in merged_body
    assert "Extra child instructions." in merged_body
