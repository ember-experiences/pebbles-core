"""Tests for the v0.2 Storage Protocol + v0.1 backwards-compat module.

v0.2 pattern (per Song's pushback on the original draft):
- `from pebbles import Storage` → the Protocol (v0.2 headline)
- `from pebbles import JsonStorage` → the concrete impl
- `from pebbles.compat import Storage` → alias to JsonStorage (v0.1-style usage)
"""

from pebbles.core.storage import Storage as ProtocolType
from pebbles.storage import JsonStorage


def test_top_level_storage_is_the_protocol():
    """v0.2: `from pebbles import Storage` is the Protocol, not the concrete class."""
    from pebbles import Storage
    # The Protocol type — same object as pebbles.core.storage.Storage
    assert Storage is ProtocolType


def test_top_level_jsonstorage_is_the_concrete_class():
    """v0.2: `from pebbles import JsonStorage` is the concrete JSON-file impl."""
    from pebbles import JsonStorage as TopLevelJson
    assert TopLevelJson is JsonStorage


def test_compat_storage_aliases_jsonstorage():
    """v0.1 callers can import the old meaning of Storage from pebbles.compat."""
    from pebbles.compat import Storage as CompatStorage
    assert CompatStorage is JsonStorage


def test_jsonstorage_satisfies_storage_protocol(tmp_path):
    """JsonStorage's method signatures satisfy the Protocol's runtime check."""
    s = JsonStorage(tmp_path / "test.db")
    assert isinstance(s, ProtocolType)


def test_compat_storage_can_construct_jsonstorage(tmp_path):
    """v0.1-style code: `Storage("path")` from pebbles.compat works as before."""
    from pebbles.compat import Storage
    s = Storage(tmp_path / "test.db")
    assert isinstance(s, JsonStorage)
    # And v0.1 methods still work
    s.mark_delivered("https://example.com/x", "alice")
    assert s.was_delivered("https://example.com/x", "alice") is True


def test_pebbles_storage_module_exports_both():
    """`pebbles.storage` re-exports both the concrete class and the Protocol."""
    from pebbles.storage import JsonStorage as JS, Storage as ProtoFromStorageModule
    assert JS is JsonStorage
    assert ProtoFromStorageModule is ProtocolType
