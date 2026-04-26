"""Tests for pebbles.core.principal.Principal."""

import os
from pathlib import Path

import pytest

from pebbles.core.principal import Principal


def test_minimal_construction():
    p = Principal(id="test", name="Test Persona", mode="ai_persona")
    assert p.id == "test"
    assert p.name == "Test Persona"
    assert p.mode == "ai_persona"
    # Hierarchy defaults are empty
    assert p.parent_id is None
    assert p.children == []
    assert p.delegation_scope == {}
    # Voice / rubric / disclosure / extra default to empty containers
    assert p.voice_corpus == []
    assert p.voice_anchors == {}
    assert p.rubric == {}
    assert p.disclosure == {}
    assert p.extra == {}


def test_mode_is_free_string():
    """D1: mode is a free string, not enum-restricted."""
    p = Principal(id="test", name="Test", mode="employer_representative")
    assert p.mode == "employer_representative"
    # Future modes don't require Core releases
    p2 = Principal(id="test2", name="Test", mode="research_assistant")
    assert p2.mode == "research_assistant"


def test_hierarchy_fields():
    p = Principal(
        id="song",
        name="Song",
        mode="ai_persona",
        children=["scout_song", "presence_song"],
        delegation_scope={
            "scout_song": {"actions": ["research", "propose_watchlist"], "auto_approve": False},
            "presence_song": {"actions": ["draft", "rate"], "auto_approve": False},
        },
    )
    assert "scout_song" in p.children
    assert p.authority_for("scout_song") == {
        "actions": ["research", "propose_watchlist"],
        "auto_approve": False,
    }
    assert p.authority_for("nonexistent_child") == {}


def test_load_child_rejects_undeclared():
    """A parent cannot load_child a child not in its declared children list."""
    p = Principal(id="parent", name="P", mode="ai_persona", children=["valid_child"])
    with pytest.raises(ValueError, match="did not declare"):
        p.load_child("undeclared_child")


def test_load_child_finds_yaml_and_sets_parent_id(tmp_path: Path):
    parent_yaml = tmp_path / "parent.yaml"
    parent_yaml.write_text(
        "id: parent_p\nname: Parent\nmode: ai_persona\nchildren: [child_p]\n"
    )
    child_yaml = tmp_path / "child_p.yaml"
    child_yaml.write_text("id: child_p\nname: Child\nmode: ai_persona\n")

    parent = Principal.from_yaml(parent_yaml)
    child = parent.load_child("child_p", search_paths=[tmp_path])
    assert child.id == "child_p"
    assert child.parent_id == "parent_p"  # auto-set by load_child


def test_load_child_preserves_explicit_parent_id(tmp_path: Path):
    """If child YAML declares parent_id explicitly, load_child does NOT overwrite."""
    parent_yaml = tmp_path / "parent.yaml"
    parent_yaml.write_text("id: parent_p\nname: P\nmode: ai_persona\nchildren: [child_p]\n")
    child_yaml = tmp_path / "child_p.yaml"
    child_yaml.write_text("id: child_p\nname: C\nmode: ai_persona\nparent_id: someone_else\n")

    parent = Principal.from_yaml(parent_yaml)
    child = parent.load_child("child_p", search_paths=[tmp_path])
    assert child.parent_id == "someone_else"


def test_from_yaml_env_var_expansion(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TEST_BLOG_URL", "https://test.example.com")
    yaml_path = tmp_path / "p.yaml"
    yaml_path.write_text(
        "id: t\nname: T\nmode: ai_persona\n"
        "voice_anchors:\n  blog: ${TEST_BLOG_URL}\n"
    )
    p = Principal.from_yaml(yaml_path)
    assert p.voice_anchors["blog"] == "https://test.example.com"


def test_from_yaml_missing_env_var_is_falsy(tmp_path: Path):
    """Missing env vars are substituted with empty string; YAML may then coerce
    that to null. Either way, the resulting value is falsy — caller must check."""
    yaml_path = tmp_path / "p.yaml"
    yaml_path.write_text(
        "id: t\nname: T\nmode: ai_persona\n"
        "voice_anchors:\n  blog: ${DEFINITELY_UNSET_ENV_VAR_XYZ}\n"
    )
    p = Principal.from_yaml(yaml_path)
    # Missing env vars produce a falsy value (YAML may parse bare "" as null)
    assert not p.voice_anchors.get("blog")


def test_from_yaml_missing_env_var_quoted_stays_empty_string(tmp_path: Path):
    """If the YAML quotes the value, it stays a string even after empty substitution."""
    yaml_path = tmp_path / "p.yaml"
    yaml_path.write_text(
        "id: t\nname: T\nmode: ai_persona\n"
        'voice_anchors:\n  blog: "${DEFINITELY_UNSET_ENV_VAR_XYZ}"\n'
    )
    p = Principal.from_yaml(yaml_path)
    assert p.voice_anchors["blog"] == ""
