"""Queue Protocol — state machine for items moving through approval.

Used by Presence (presence_queue) and Scout (scout_candidates / scout watchlist proposals).
The state machine itself is universal; storage is the consumer's choice (in-memory,
SQLite, Supabase).
"""

import copy
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Protocol


class QueueStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"


VALID_TRANSITIONS: dict[QueueStatus, set[QueueStatus]] = {
    QueueStatus.PENDING: {QueueStatus.APPROVED, QueueStatus.EDITED, QueueStatus.REJECTED},
    QueueStatus.APPROVED: {QueueStatus.SENT, QueueStatus.FAILED},
    QueueStatus.EDITED: {QueueStatus.SENT, QueueStatus.FAILED},
    QueueStatus.REJECTED: set(),  # terminal
    QueueStatus.SENT: set(),       # terminal
    QueueStatus.FAILED: {QueueStatus.PENDING},  # retry path
}


class InvalidTransitionError(Exception):
    """Raised when transition() is called with an illegal status change."""

    def __init__(self, current: QueueStatus, requested: QueueStatus, item_id: str):
        self.current = current
        self.requested = requested
        self.item_id = item_id
        super().__init__(
            f"Invalid transition for item {item_id}: {current.value} -> {requested.value}. "
            f"Allowed from {current.value}: {sorted(s.value for s in VALID_TRANSITIONS[current])}"
        )


class Queue(Protocol):
    """Protocol for a principal-scoped queue with state machine."""

    def enqueue(self, principal_id: str, payload: dict) -> str:
        """Add a new item with status PENDING. Returns the item id."""
        ...

    def get(self, item_id: str) -> Optional[dict]:
        """Read an item by id. Returns None if not found."""
        ...

    def transition(self, item_id: str, to_status: QueueStatus, **fields) -> bool:
        """Move an item to a new status, validating against VALID_TRANSITIONS.

        Extra fields (final_content, reject_reason, sent_at, etc.) are merged
        into the item record.

        Returns True on success.
        Raises InvalidTransitionError on illegal transition.
        Raises KeyError if item_id not found.
        """
        ...

    def list(
        self,
        principal_id: str,
        status: Optional[QueueStatus] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List items for a principal, newest first, optionally filtered by status."""
        ...


class InMemoryQueue:
    """Reference impl. Dict-backed. For tests + dev.

    Storage-backed impls (SqliteQueue, SupabaseQueue) implement the same
    Protocol with persistent backends.
    """

    def __init__(self):
        self._items: dict[str, dict] = {}

    def enqueue(self, principal_id: str, payload: dict) -> str:
        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        self._items[item_id] = {
            "id": item_id,
            "principal_id": principal_id,
            "status": QueueStatus.PENDING.value,
            "payload": dict(payload),
            "created_at": now,
            "updated_at": now,
        }
        return item_id

    def get(self, item_id: str) -> Optional[dict]:
        item = self._items.get(item_id)
        return copy.deepcopy(item) if item else None  # deep copy — payload is a nested dict

    def transition(self, item_id: str, to_status: QueueStatus, **fields) -> bool:
        if item_id not in self._items:
            raise KeyError(f"Queue item not found: {item_id}")

        item = self._items[item_id]
        current = QueueStatus(item["status"])

        if to_status not in VALID_TRANSITIONS[current]:
            raise InvalidTransitionError(current, to_status, item_id)

        item["status"] = to_status.value
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        for k, v in fields.items():
            item[k] = v
        return True

    def list(self, principal_id, status=None, limit=50) -> list[dict]:
        items = [i for i in self._items.values() if i["principal_id"] == principal_id]
        if status is not None:
            items = [i for i in items if i["status"] == status.value]
        items.sort(key=lambda i: i["created_at"], reverse=True)
        return [copy.deepcopy(i) for i in items[:limit]]
