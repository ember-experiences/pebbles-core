"""Tests for the v0.2 Storage Protocol + v0.1 backwards-compat alias."""

from pebbles.core.storage import Storage as StorageProtocol
from pebbles.storage import JsonStorage, Storage as v01_alias


def test_v01_alias_points_to_jsonstorage():
    """v0.1 callers using `from pebbles.storage import Storage` keep working."""
    assert v01_alias is JsonStorage


def test_jsonstorage_satisfies_protocol(tmp_path):
    """JsonStorage's method signatures satisfy the Protocol's runtime check."""
    s = JsonStorage(tmp_path / "test.db")
    assert isinstance(s, StorageProtocol)


def test_v02_top_level_alias_exposes_jsonstorage_via_storage():
    """`from pebbles import Storage` (v0.1 ergonomic) gets JsonStorage."""
    from pebbles import Storage
    assert Storage is JsonStorage
