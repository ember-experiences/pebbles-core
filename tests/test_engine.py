"""
Tests for pebble engine, sources, and storage.
"""

import pytest
import asyncio
from pathlib import Path
from pebbles.models import Pebble, Recipient, SourceType, DeliveryMethod
from pebbles.sources import HackerNewsSource
from pebbles.storage import PebbleStorage
from pebbles.engine import PebbleEngine
from pebbles.config import Settings


@pytest.fixture
def temp_storage(tmp_path):
    """Temporary database for testing."""
    db_path = tmp_path / "test_pebbles.db"
    return PebbleStorage(db_path)


@pytest.fixture
def test_settings(tmp_path):
    """Settings with test database."""
    settings = Settings()
    settings.storage_path = tmp_path / "test_pebbles.db"
    settings.recipients = [
        Recipient(
            name="Test User",
            telegram_chat_id=123456,
            interests=["AI", "rust", "databases"],
            delivery_method=DeliveryMethod.TELEGRAM
        )
    ]
    return settings


def test_hackernews_fetch():
    """Test HN source fetches and parses stories."""
    source = HackerNewsSource(max_stories=5)
    try:
        pebbles = source.fetch("top")
        
        assert len(pebbles) > 0
        assert all(isinstance(p, Pebble) for p in pebbles)
        assert all(p.source == SourceType.HACKERNEWS for p in pebbles)
        assert all(p.url for p in pebbles)
        assert all(p.title for p in pebbles)
    finally:
        source.close()


def test_storage_dedup(temp_storage):
    """Test storage prevents duplicate deliveries."""
    url = "https://example.com/article"
    recipient = "Test User"
    
    # First delivery
    assert not temp_storage.has_delivered(url, recipient)
    assert temp_storage.mark_delivered(url, recipient) is True
    
    # Second attempt
    assert temp_storage.has_delivered(url, recipient)
    assert temp_storage.mark_delivered(url, recipient) is False


def test_interest_matching(test_settings):
    """Test engine matches pebbles to recipient interests."""
    engine = PebbleEngine(test_settings)
    
    pebbles = [
        Pebble(
            url="https://example.com/ai",
            title="New AI breakthrough in transformers",
            summary="",
            source=SourceType.HACKERNEWS
        ),
        Pebble(
            url="https://example.com/unrelated",
            title="How to bake bread",
            summary="",
            source=SourceType.HACKERNEWS
        )
    ]
    
    matches = engine._match_interests(pebbles)
    
    # Should match first pebble (contains "AI")
    assert len(matches) == 1
    assert matches[0][0].url == "https://example.com/ai"


@pytest.mark.asyncio
async def test_full_pipeline_dry_run(test_settings):
    """Test full engine pipeline (without actual Telegram delivery)."""
    # This test would require mocking TelegramDelivery
    # For now, just verify engine initializes
    engine = PebbleEngine(test_settings)
    assert engine.storage is not None
    assert engine.delivery is not None