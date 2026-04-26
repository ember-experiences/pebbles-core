"""Tests for pebbles.core.queue."""

import pytest

from pebbles.core.queue import (
    InMemoryQueue,
    InvalidTransitionError,
    QueueStatus,
    VALID_TRANSITIONS,
)


def test_enqueue_returns_id():
    q = InMemoryQueue()
    item_id = q.enqueue("song", {"text": "hello"})
    assert isinstance(item_id, str)
    assert len(item_id) > 0


def test_enqueue_creates_pending_item():
    q = InMemoryQueue()
    item_id = q.enqueue("song", {"text": "hello"})
    item = q.get(item_id)
    assert item is not None
    assert item["status"] == "pending"
    assert item["principal_id"] == "song"
    assert item["payload"] == {"text": "hello"}


def test_get_returns_none_for_unknown_id():
    q = InMemoryQueue()
    assert q.get("nonexistent") is None


def test_get_returns_copy_not_reference():
    """Mutating the returned dict must not affect the queue's internal state."""
    q = InMemoryQueue()
    item_id = q.enqueue("song", {"text": "v1"})
    item = q.get(item_id)
    item["payload"]["text"] = "MUTATED"
    fresh = q.get(item_id)
    assert fresh["payload"]["text"] == "v1"


def test_valid_transition_pending_to_approved():
    q = InMemoryQueue()
    item_id = q.enqueue("song", {})
    assert q.transition(item_id, QueueStatus.APPROVED) is True
    assert q.get(item_id)["status"] == "approved"


def test_valid_transition_with_extra_fields():
    q = InMemoryQueue()
    item_id = q.enqueue("song", {})
    q.transition(item_id, QueueStatus.EDITED, final_content="edited", semantic_edit_distance=0.18)
    item = q.get(item_id)
    assert item["status"] == "edited"
    assert item["final_content"] == "edited"
    assert item["semantic_edit_distance"] == 0.18


def test_invalid_transition_raises():
    """D3: invalid transitions raise InvalidTransitionError, not return False."""
    q = InMemoryQueue()
    item_id = q.enqueue("song", {})
    # PENDING -> SENT is not allowed
    with pytest.raises(InvalidTransitionError) as exc_info:
        q.transition(item_id, QueueStatus.SENT)
    assert exc_info.value.current == QueueStatus.PENDING
    assert exc_info.value.requested == QueueStatus.SENT


def test_transition_from_terminal_state_raises():
    q = InMemoryQueue()
    item_id = q.enqueue("song", {})
    q.transition(item_id, QueueStatus.REJECTED)
    # REJECTED is terminal; nothing can leave it
    for status in QueueStatus:
        with pytest.raises(InvalidTransitionError):
            q.transition(item_id, status)


def test_failed_can_retry_to_pending():
    """The retry path: APPROVED -> FAILED -> PENDING."""
    q = InMemoryQueue()
    item_id = q.enqueue("song", {})
    q.transition(item_id, QueueStatus.APPROVED)
    q.transition(item_id, QueueStatus.FAILED)
    q.transition(item_id, QueueStatus.PENDING)  # retry
    assert q.get(item_id)["status"] == "pending"


def test_transition_unknown_id_raises_keyerror():
    q = InMemoryQueue()
    with pytest.raises(KeyError):
        q.transition("nonexistent", QueueStatus.APPROVED)


def test_list_filters_by_principal():
    q = InMemoryQueue()
    q.enqueue("song", {})
    q.enqueue("song", {})
    q.enqueue("kai", {})
    song_items = q.list("song")
    kai_items = q.list("kai")
    assert len(song_items) == 2
    assert len(kai_items) == 1


def test_list_filters_by_status():
    q = InMemoryQueue()
    a = q.enqueue("song", {})
    b = q.enqueue("song", {})
    q.transition(a, QueueStatus.APPROVED)
    pending = q.list("song", status=QueueStatus.PENDING)
    approved = q.list("song", status=QueueStatus.APPROVED)
    assert len(pending) == 1 and pending[0]["id"] == b
    assert len(approved) == 1 and approved[0]["id"] == a


def test_list_orders_newest_first():
    """Newest items appear first in list output."""
    import time

    q = InMemoryQueue()
    a = q.enqueue("song", {})
    time.sleep(0.001)  # ensure timestamp ordering
    b = q.enqueue("song", {})
    items = q.list("song")
    assert items[0]["id"] == b
    assert items[1]["id"] == a


def test_valid_transitions_table_completeness():
    """Every QueueStatus appears as a key in VALID_TRANSITIONS."""
    for status in QueueStatus:
        assert status in VALID_TRANSITIONS
