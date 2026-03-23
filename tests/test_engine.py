"""Tests for pebble engine."""
import pytest
from pathlib import Path
import tempfile

from pebbles.engine import Engine
from pebbles.storage import Storage


class MockSource:
    """Mock source for testing."""
    
    def __init__(self, items=None, should_fail=False):
        self.items = items or []
        self.should_fail = should_fail
        
    def fetch(self):
        if self.should_fail:
            raise Exception("Mock source failure")
        return self.items


class MockMatcher:
    """Mock matcher that accepts everything."""
    
    def match(self, item):
        return True


class MockFilter:
    """Mock filter that accepts everything."""
    
    def filter(self, item):
        return True


class MockDelivery:
    """Mock delivery that tracks what was delivered."""
    
    def __init__(self):
        self.delivered = []
        
    def deliver(self, item, recipient):
        self.delivered.append((item, recipient))
        return True


def test_engine_delivers_new_items():
    """Test that engine delivers new items."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        storage = Storage(str(db_path))
        
        items = [
            {'url': 'https://example.com/1', 'title': 'Test 1'},
            {'url': 'https://example.com/2', 'title': 'Test 2'},
        ]
        
        source = MockSource(items)
        matcher = MockMatcher()
        filter_obj = MockFilter()
        delivery = MockDelivery()
        
        engine = Engine(
            sources=[source],
            matcher=matcher,
            filter=filter_obj,
            delivery=delivery,
            recipient='test_user',
            storage=storage
        )
        
        count = engine.run()
        
        assert count == 2
        assert len(delivery.delivered) == 2


def test_engine_deduplicates():
    """Test that engine doesn't deliver duplicates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        storage = Storage(str(db_path))
        
        items = [
            {'url': 'https://example.com/1', 'title': 'Test 1'},
        ]
        
        source = MockSource(items)
        matcher = MockMatcher()
        filter_obj = MockFilter()
        delivery = MockDelivery()
        
        engine = Engine(
            sources=[source],
            matcher=matcher,
            filter=filter_obj,
            delivery=delivery,
            recipient='test_user',
            storage=storage
        )
        
        # First run delivers
        count1 = engine.run()
        assert count1 == 1
        
        # Second run should skip (already delivered)
        delivery.delivered.clear()
        count2 = engine.run()
        assert count2 == 0
        assert len(delivery.delivered) == 0


def test_engine_handles_source_failure():
    """Test that engine continues when a source fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        storage = Storage(str(db_path))
        
        # First source fails, second source succeeds
        failing_source = MockSource(should_fail=True)
        working_source = MockSource([
            {'url': 'https://example.com/1', 'title': 'Test 1'}
        ])
        
        matcher = MockMatcher()
        filter_obj = MockFilter()
        delivery = MockDelivery()
        
        engine = Engine(
            sources=[failing_source, working_source],
            matcher=matcher,
            filter=filter_obj,
            delivery=delivery,
            recipient='test_user',
            storage=storage
        )
        
        # Should deliver from working source despite failing source
        count = engine.run()
        assert count == 1
        assert len(delivery.delivered) == 1


def test_engine_skips_items_without_url():
    """Test that engine skips items missing URL."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        storage = Storage(str(db_path))
        
        items = [
            {'title': 'No URL'},  # Missing URL
            {'url': 'https://example.com/1', 'title': 'Valid'},
        ]
        
        source = MockSource(items)
        matcher = MockMatcher()
        filter_obj = MockFilter()
        delivery = MockDelivery()
        
        engine = Engine(
            sources=[source],
            matcher=matcher,
            filter=filter_obj,
            delivery=delivery,
            recipient='test_user',
            storage=storage
        )
        
        count = engine.run()
        
        # Should only deliver the valid item
        assert count == 1
        assert delivery.delivered[0][0]['url'] == 'https://example.com/1'