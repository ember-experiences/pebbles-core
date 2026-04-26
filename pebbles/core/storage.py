"""Storage Protocol — backwards-compatible with v0.1 Storage class.

v0.1 had a concrete `pebbles.storage.Storage` (JSON file). v0.2 protocol-izes
the shape so SQLite + Supabase impls can slot in alongside.

The Protocol is named `Storage` here. The v0.1 concrete class is renamed to
`JsonStorage` in pebbles.storage, with a `Storage = JsonStorage` alias preserved
for backwards compat.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """Protocol for delivery-tracking storage.

    Compatible with v0.1's Storage method signatures so existing impls
    satisfy this Protocol without modification.
    """

    def mark_delivered(self, url: str, recipient: str) -> None:
        """Record that an item at `url` was delivered to `recipient`."""
        ...

    def was_delivered(self, url: str, recipient: str) -> bool:
        """Check if `url` was already delivered to `recipient`."""
        ...

    def delivered_today(self, recipient: str) -> int:
        """Count items delivered to `recipient` in the last 24h."""
        ...

    def get_stats(self) -> dict:
        """Return delivery statistics. At minimum: total_deliveries, last_24h."""
        ...
