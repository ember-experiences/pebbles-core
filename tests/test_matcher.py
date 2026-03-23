"""Tests for interest matching."""

import pytest
from datetime import datetime

from pebbles.models import Pebble, Interest
from pebbles.matcher import InterestMatcher


@pytest.fixture
def sample_pebble():
    """Create a sample pebble for testing."""
    return Pebble(
        title="New Python 3.12 Features",
        url="https://example.com/python312",
        description="Learn about the latest features in Python 3.12 including better error messages",
        source="test",
        timestamp=datetime.now()
    )


@pytest.fixture
def sample_interest():
    """Create a sample interest for testing."""
    return Interest(
        name="Python Development",
        tags=["python", "programming"],
        keywords=["python3", "features"],
        negative_keywords=["deprecated"],
        priority=2
    )


def test_keyword_matching_tags(sample_pebble, sample_interest):
    """Test keyword matching with tags."""
    matcher = InterestMatcher(use_semantic=False)
    
    assert matcher.is_match(sample_pebble, sample_interest)
    score = matcher.score(sample_pebble, sample_interest)
    assert score == 1.0  # Tag match gets 1.0


def test_keyword_matching_keywords(sample_pebble):
    """Test keyword matching with keywords."""
    interest = Interest(
        name="Python",
        keywords=["python3"],
        priority=1
    )
    matcher = InterestMatcher(use_semantic=False)
    
    assert matcher.is_match(sample_pebble, interest)
    score = matcher.score(sample_pebble, interest)
    assert score == 0.7  # Keyword match gets 0.7


def test_negative_keywords_exclusion(sample_pebble):
    """Test negative keywords exclude matches."""
    interest = Interest(
        name="Python",
        tags=["python"],
        negative_keywords=["error"],  # "error" is in description
        priority=1
    )
    matcher = InterestMatcher(use_semantic=False)
    
    assert not matcher.is_match(sample_pebble, interest)
    score = matcher.score(sample_pebble, interest)
    assert score == 0.0


def test_no_match():
    """Test pebble that doesn't match."""
    pebble = Pebble(
        title="JavaScript Tutorial",
        url="https://example.com/js",
        description="Learn JavaScript basics",
        source="test"
    )
    interest = Interest(
        name="Python",
        tags=["python"],
        priority=1
    )
    matcher = InterestMatcher(use_semantic=False)
    
    assert not matcher.is_match(pebble, interest)
    score = matcher.score(pebble, interest)
    assert score == 0.0


def test_priority_field():
    """Test interest priority field."""
    interest = Interest(
        name="Critical",
        tags=["urgent"],
        priority=3
    )
    assert interest.priority == 3
    
    # Default priority
    interest2 = Interest(name="Normal", tags=["info"])
    assert interest2.priority == 1


def test_semantic_fallback():
    """Test semantic mode falls back to keyword if unavailable."""
    matcher = InterestMatcher(use_semantic=True)  # Will fail to load model in test
    
    pebble = Pebble(
        title="Python Tutorial",
        url="https://example.com",
        description="Learn Python",
        source="test"
    )
    interest = Interest(
        name="Python",
        tags=["python"],
        priority=1
    )
    
    # Should fall back to keyword matching
    assert matcher.is_match(pebble, interest)


def test_negative_keywords_alias():
    """Test that 'exclude' is aliased to 'negative_keywords'."""
    interest = Interest(
        name="Test",
        tags=["test"],
        exclude=["bad"]  # Use old 'exclude' field
    )
    assert interest.negative_keywords == ["bad"]
    
    # Test matching with exclude
    pebble = Pebble(
        title="Test with bad content",
        url="https://example.com",
        description="Contains bad keyword",
        source="test"
    )
    matcher = InterestMatcher()
    assert not matcher.is_match(pebble, interest)"""Tests for InterestMatcher."""

import pytest
from datetime import datetime

from pebbles.matcher import InterestMatcher
from pebbles.models import Interest, Pebble


@pytest.fixture
def matcher():
    return InterestMatcher(use_semantic=False)


@pytest.fixture
def sample_pebble():
    return Pebble(
        title="New Python 3.12 Release",
        url="https://example.com/python",
        content="Python 3.12 includes performance improvements",
        source="hackernews",
        timestamp=datetime.utcnow()
    )


def test_keyword_match_by_tag(matcher, sample_pebble):
    """Test matching by tag."""
    interest = Interest(
        name="Python News",
        tags=["python"],
        keywords=[]
    )
    
    assert matcher.is_match(sample_pebble, interest)
    assert matcher.score(sample_pebble, interest) == 1.0


def test_keyword_match_by_keyword(matcher, sample_pebble):
    """Test matching by keyword."""
    interest = Interest(
        name="Python News",
        tags=[],
        keywords=["python"]
    )
    
    assert matcher.is_match(sample_pebble, interest)
    assert matcher.score(sample_pebble, interest) == 1.0


def test_negative_keyword_blocks_match(matcher, sample_pebble):
    """Test that negative keywords prevent matches."""
    interest = Interest(
        name="Python News",
        tags=["python"],
        keywords=[],
        negative_keywords=["3.12"]
    )
    
    assert not matcher.is_match(sample_pebble, interest)


def test_no_match_when_no_keywords_present(matcher):
    """Test that non-matching content returns false."""
    pebble = Pebble(
        title="JavaScript Framework Update",
        url="https://example.com/js",
        content="New React features",
        source="hackernews",
        timestamp=datetime.utcnow()
    )
    
    interest = Interest(
        name="Python News",
        tags=["python"],
        keywords=["django", "flask"]
    )
    
    assert not matcher.is_match(pebble, interest)
    assert matcher.score(pebble, interest) == 0.0


def test_priority_field_exists():
    """Test that Interest supports priority field."""
    interest = Interest(
        name="Critical Updates",
        tags=["security"],
        priority=3
    )
    
    assert interest.priority == 3


def test_negative_keywords_alias():
    """Test that 'exclude' works as alias for negative_keywords."""
    interest = Interest(
        name="Test",
        tags=["python"],
        exclude=["tutorial"]
    )
    
    assert interest.negative_keywords == ["tutorial"]