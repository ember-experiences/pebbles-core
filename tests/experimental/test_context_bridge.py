"""Tests for ContextBridge — specifically the drive-home → photo failure scenario."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from pebbles.recent_context import RecentContextStore, RecentContextEntry
from pebbles.entity_extract import extract_entities_fast
from pebbles.context_bridge import ContextBridge


@pytest.fixture
def tmp_store(tmp_path):
    return RecentContextStore(store_path=tmp_path / "recent_context.json")


@pytest.fixture
def bridge(tmp_store):
    return ContextBridge(store=tmp_store)


# ── The exact failure scenario ────────────────────────────────────────────────

def test_robert_surf_photo_failure_scenario(bridge):
    """Regression test for the Doheny dawn patrol / Robert photo disconnect.

    Step 1: Song's assistant learns about Robert's surf session (session A).
    Step 2: Robert sends a photo (session B).
    Without the bridge: session B knows nothing.
    With the bridge: the context is injected.
    """
    # Session A: drive-home conversation
    bridge.record(
        entities=["robert", "doheny"],
        summary="Robert just finished a dawn patrol surf session at Doheny. "
                "Song learned about it during her drive home.",
        session_id="drive-home-voice",
        ttl_minutes=180,
    )

    # Session B: Robert's photo arrives
    enriched = bridge.enrich_message(
        message="Robert sent a photo of himself on a wave.",
        sender_entities=["robert"],
    )

    # The context from session A must be present in session B's prompt
    assert "dawn patrol" in enriched
    assert "Doheny" in enriched or "doheny" in enriched
    assert "Recent context" in enriched


def test_no_false_injection_for_unrelated_person(bridge):
    """Context about Robert should not inject when Alice sends a message."""
    bridge.record(
        entities=["robert", "doheny"],
        summary="Robert is surfing at Doheny.",
        session_id="drive-home-voice",
    )

    enriched = bridge.enrich_message(
        message="Alice sent a message asking about dinner.",
        sender_entities=["alice"],
    )

    # No surf context should appear for Alice
    assert "dawn patrol" not in enriched
    assert "Doheny" not in enriched
    assert enriched == "Alice sent a message asking about dinner."


def test_expired_context_not_injected(tmp_path):
    """Context past its TTL must not inject — stale context is worse than none."""
    store = RecentContextStore(store_path=tmp_path / "ctx.json")

    entry = RecentContextEntry(
        id="old-entry",
        entities=["robert"],
        summary="Robert is surfing.",
        source_session="test",
        created_at=datetime.now() - timedelta(hours=5),
        ttl_minutes=60,  # expired 4 hours ago
    )
    # Directly write expired entry to disk (bypassing is_live check)
    import json
    with open(store.store_path, "w") as f:
        json.dump([entry.model_dump(mode="json")], f, default=str)

    bridge = ContextBridge(store=store)
    enriched = bridge.enrich_message("Robert sent a photo.", sender_entities=["robert"])

    assert "Robert is surfing" not in enriched


# ── Entity extraction ─────────────────────────────────────────────────────────

def test_fast_entity_extraction_catches_names():
    entities = extract_entities_fast(
        "Robert texted me from Doheny after his dawn patrol session."
    )
    assert "robert" in entities
    assert "doheny" in entities


def test_fast_entity_extraction_no_false_positives():
    entities = extract_entities_fast("he sent a photo of the wave")
    # No proper nouns → minimal/empty extraction (no hallucinated names)
    assert "robert" not in entities
    assert "doheny" not in entities


# ── Relevance scoring / recency bias ─────────────────────────────────────────

def test_recent_entry_scores_higher_than_old(tmp_store):
    """A 10-min-old entry about Robert scores higher than a 3-hour-old one."""
    recent = RecentContextEntry(
        id="recent",
        entities=["robert"],
        summary="Robert is surfing now.",
        source_session="a",
        created_at=datetime.now() - timedelta(minutes=10),
        ttl_minutes=240,
    )
    old = RecentContextEntry(
        id="old",
        entities=["robert"],
        summary="Robert was at the gym.",
        source_session="b",
        created_at=datetime.now() - timedelta(minutes=180),
        ttl_minutes=240,
    )

    recent_score = recent.relevance_score(["robert"])
    old_score = old.relevance_score(["robert"])

    assert recent_score > old_score


def test_multi_entity_overlap_boosts_score():
    """Matching both 'robert' and 'doheny' scores higher than matching just one."""
    entry = RecentContextEntry(
        id="e1",
        entities=["robert", "doheny"],
        summary="Robert at Doheny.",
        source_session="a",
        ttl_minutes=240,
    )

    single_match = entry.relevance_score(["robert"])
    double_match = entry.relevance_score(["robert", "doheny"])

    assert double_match > single_match


# ── record_from_text convenience ──────────────────────────────────────────────

def test_record_from_text_extracts_and_stores(bridge):
    entities = bridge.record_from_text(
        text="Robert just got out of the water at Doheny.",
        summary="Robert finished dawn patrol at Doheny.",
        session_id="drive-home-voice",
    )

    assert "robert" in entities
    assert "doheny" in entities

    results = bridge.store.query(["robert"])
    assert len(results) == 1
    assert "dawn patrol" in results[0].summary
