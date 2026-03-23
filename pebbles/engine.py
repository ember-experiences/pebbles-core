"""Core pebble discovery and delivery engine."""
from typing import Protocol, List, Dict, Any
from datetime import datetime

from pebbles.storage import Storage
from pebbles.log import get_logger

logger = get_logger(__name__)


class Source(Protocol):
    """Protocol for pebble sources."""
    
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw items from source.
        
        Returns:
            List of raw item dicts with at least 'url' and 'title'
        """
        ...


class Matcher(Protocol):
    """Protocol for interest matchers."""
    
    def match(self, item: Dict[str, Any]) -> bool:
        """Check if item matches user interests.
        
        Args:
            item: Raw item dict
            
        Returns:
            True if item matches interests
        """
        ...


class Filter(Protocol):
    """Protocol for content filters."""
    
    def filter(self, item: Dict[str, Any]) -> bool:
        """Check if item should be filtered out.
        
        Args:
            item: Raw item dict
            
        Returns:
            True if item should be kept, False to filter
        """
        ...


class Delivery(Protocol):
    """Protocol for delivery adapters."""
    
    def deliver(self, item: Dict[str, Any], recipient: str) -> bool:
        """Deliver pebble to recipient.
        
        Args:
            item: Matched and filtered item
            recipient: Recipient identifier (e.g. telegram user_id)
            
        Returns:
            True if delivery succeeded
        """
        ...


class Engine:
    """Pebble discovery and delivery engine."""
    
    def __init__(
        self,
        sources: List[Source],
        matcher: Matcher,
        filter: Filter,
        delivery: Delivery,
        recipient: str,
        storage: Storage
    ):
        self.sources = sources
        self.matcher = matcher
        self.filter = filter
        self.delivery = delivery
        self.recipient = recipient
        self.storage = storage
        
    def run(self) -> int:
        """Run one discovery cycle.
        
        Returns:
            Number of pebbles delivered
        """
        delivered_count = 0
        
        for source in self.sources:
            try:
                logger.info(f"Fetching from source: {source.__class__.__name__}")
                items = source.fetch()
                logger.info(f"Fetched {len(items)} items from {source.__class__.__name__}")
                
                for item in items:
                    url = item.get('url')
                    if not url:
                        logger.warning(f"Item missing URL, skipping: {item}")
                        continue
                        
                    # Dedup check
                    if self.storage.was_delivered(url, self.recipient):
                        continue
                        
                    # Match against interests
                    if not self.matcher.match(item):
                        continue
                        
                    # Apply filters
                    if not self.filter.filter(item):
                        logger.info(f"Item filtered: {item.get('title', url)}")
                        continue
                        
                    # Deliver
                    if self.delivery.deliver(item, self.recipient):
                        self.storage.mark_delivered(url, self.recipient)
                        delivered_count += 1
                        logger.info(f"Delivered: {item.get('title', url)} to {self.recipient}")
                    else:
                        logger.error(f"Delivery failed: {item.get('title', url)}")
                        
            except Exception as e:
                logger.error(f"Source {source.__class__.__name__} failed: {e}", exc_info=True)
                continue
                
        logger.info(f"Discovery cycle complete. Delivered {delivered_count} pebbles.")
        return delivered_count"""Pebble distribution engine.

Fetches pebbles from configured sources and delivers them to recipients.
"""

from datetime import datetime
from pebbles.config import Config
from pebbles.log import get_logger
from pebbles.models import Pebble
from pebbles.delivery import TwilioDelivery
from pebbles.sources import (
    HackerNewsSource,
    RedditSource,
    RSSSource,
    YouTubeSource,
    LetterboxdSource,
)

logger = get_logger(__name__)


class PebbleEngine:
    """Orchestrates pebble fetching and delivery."""
    
    def __init__(self, config: Config):
        self.config = config
        self.delivery = TwilioDelivery(
            account_sid=config.twilio_account_sid,
            auth_token=config.twilio_auth_token,
            from_number=config.twilio_from_number,
        )
        self.sources = self._init_sources()
    
    def _init_sources(self) -> list:
        """Initialize all configured sources."""
        sources = []
        
        # HackerNews (always enabled)
        sources.append(HackerNewsSource())
        
        # Reddit (opt-in)
        if self.config.reddit_subreddits:
            sources.append(RedditSource(self.config.reddit_subreddits))
        
        # RSS (opt-in)
        if self.config.rss_feeds:
            sources.append(RSSSource(self.config.rss_feeds))
        
        # YouTube (opt-in, requires API key)
        if self.config.youtube_queries and self.config.youtube_api_key:
            sources.append(YouTubeSource(
                self.config.youtube_api_key,
                self.config.youtube_queries
            ))
        
        # Letterboxd (opt-in)
        if self.config.letterboxd_usernames:
            sources.append(LetterboxdSource(self.config.letterboxd_usernames))
        
        logger.info(f"Initialized {len(sources)} pebble sources")
        return sources
    
    def _fetch_pebbles(self) -> list[Pebble]:
        """Fetch pebbles from all configured sources."""
        all_pebbles = []
        
        for source in self.sources:
            try:
                logger.info(f"Fetching from {source.__class__.__name__}")
                pebbles = source.fetch()
                all_pebbles.extend(pebbles)
                logger.info(f"Got {len(pebbles)} pebbles from {source.__class__.__name__}")
            except Exception as e:
                logger.error(f"Source {source.__class__.__name__} failed: {e}")
                continue
        
        logger.info(f"Total pebbles fetched: {len(all_pebbles)}")
        return all_pebbles
    
    def run(self):
        """Run one cycle: fetch pebbles and deliver to recipients."""
        logger.info("Starting pebble run")
        
        pebbles = self._fetch_pebbles()
        
        if not pebbles:
            logger.warning("No pebbles fetched, nothing to deliver")
            return
        
        # Simple round-robin distribution
        for i, pebble in enumerate(pebbles):
            recipient = self.config.recipients[i % len(self.config.recipients)]
            
            message = f"{pebble.content}\n\n{pebble.url}"
            
            try:
                self.delivery.send(recipient, message)
                logger.info(f"Delivered pebble to {recipient}")
            except Exception as e:
                logger.error(f"Failed to deliver to {recipient}: {e}")
        
        logger.info("Pebble run complete")
    
    def close(self):
        """Clean up resources."""
        for source in self.sources:
            source.close()
        self.delivery.close()"""Pebble collection engine - coordinates sources and delivery."""

from datetime import datetime
from typing import List

from .models import Pebble
from .sources import (
    HackerNewsSource,
    RedditSource,
    RSSSource,
    YouTubeSource,
    LetterboxdSource
)
from .storage import PebbleStorage
from .log import get_logger

logger = get_logger(__name__)


class PebbleEngine:
    """Coordinates pebble collection from multiple sources."""
    
    def __init__(self, config):
        """Initialize the engine with configuration."""
        self.config = config
        self.storage = PebbleStorage(config.db_path)
        self.sources = []
        
        # Initialize configured sources (opt-in)
        if hasattr(config, 'hackernews_enabled') and config.hackernews_enabled:
            self.sources.append(HackerNewsSource())
            logger.info("Initialized HackerNewsSource")
        
        if hasattr(config, 'reddit_subreddits') and config.reddit_subreddits:
            self.sources.append(RedditSource(config.reddit_subreddits))
            logger.info(f"Initialized RedditSource with {len(config.reddit_subreddits)} subreddits")
        
        if hasattr(config, 'rss_feeds') and config.rss_feeds:
            self.sources.append(RSSSource(config.rss_feeds))
            logger.info(f"Initialized RSSSource with {len(config.rss_feeds)} feeds")
        
        if hasattr(config, 'youtube_queries') and config.youtube_queries:
            api_key = getattr(config, 'youtube_api_key', None)
            self.sources.append(YouTubeSource(api_key, config.youtube_queries))
            logger.info(f"Initialized YouTubeSource with {len(config.youtube_queries)} queries")
        
        if hasattr(config, 'letterboxd_usernames') and config.letterboxd_usernames:
            self.sources.append(LetterboxdSource(config.letterboxd_usernames))
            logger.info(f"Initialized LetterboxdSource following {len(config.letterboxd_usernames)} users")
    
    def _fetch_pebbles(self) -> List[Pebble]:
        """Fetch pebbles from all sources."""
        all_pebbles = []
        
        for source in self.sources:
            try:
                logger.info(f"Fetching from {source.__class__.__name__}")
                pebbles = source.fetch()
                all_pebbles.extend(pebbles)
                logger.info(f"Got {len(pebbles)} pebbles from {source.__class__.__name__}")
            except Exception as e:
                logger.error(f"Source {source.__class__.__name__} failed: {e}")
        
        return all_pebbles
    
    def collect(self) -> int:
        """Run collection cycle - fetch and store new pebbles."""
        logger.info("Starting pebble collection cycle")
        
        pebbles = self._fetch_pebbles()
        
        if not pebbles:
            logger.warning("No pebbles collected this cycle")
            return 0
        
        stored = 0
        for pebble in pebbles:
            if self.storage.store_pebble(pebble):
                stored += 1
        
        logger.info(f"Collection complete: {stored} new pebbles stored")
        return stored
    
    def get_unsent_pebbles(self, recipient: str, limit: int = 10) -> List[Pebble]:
        """Get pebbles not yet sent to a recipient."""
        return self.storage.get_unsent_pebbles(recipient, limit)
    
    def mark_sent(self, pebble_id: int, recipient: str):
        """Mark a pebble as sent to a recipient."""
        self.storage.mark_sent(pebble_id, recipient)
    
    def get_stats(self) -> dict:
        """Get collection statistics."""
        return self.storage.get_stats()
    
    def close(self):
        """Clean up resources."""
        for source in self.sources:
            source.close()
        self.storage.close()"""Core pebble collection and delivery engine."""

import logging
from datetime import datetime
from typing import Optional

from pebbles.config import PebblesConfig
from pebbles.models import Pebble, Recipient
from pebbles.matcher import InterestMatcher
from pebbles.storage import PebbleStorage
from pebbles.sources import (
    HackerNewsSource,
    RedditSource,
    RSSSource,
    YouTubeSource,
    LetterboxdSource,
)

logger = logging.getLogger(__name__)


class PebbleEngine:
    """Main engine for collecting and delivering pebbles."""
    
    def __init__(self, config: PebblesConfig, storage: PebbleStorage):
        """Initialize the engine."""
        self.config = config
        self.storage = storage
        self.matcher = InterestMatcher(
            use_semantic=config.use_semantic_matching,
            semantic_threshold=config.semantic_threshold
        )
        self.sources = []
        self._initialize_sources()
    
    def _initialize_sources(self):
        """Initialize configured sources."""
        # HackerNews (always enabled)
        self.sources.append(HackerNewsSource())
        logger.info("Initialized HackerNewsSource")
        
        # Reddit (if configured)
        if self.config.reddit_subreddits:
            self.sources.append(RedditSource(self.config.reddit_subreddits))
            logger.info(f"Initialized RedditSource with {len(self.config.reddit_subreddits)} subreddits")
        
        # RSS (if configured)
        if self.config.rss_feeds:
            self.sources.append(RSSSource(self.config.rss_feeds))
            logger.info(f"Initialized RSSSource with {len(self.config.rss_feeds)} feeds")
        
        # YouTube (if configured)
        if self.config.youtube_queries and self.config.youtube_api_key:
            self.sources.append(YouTubeSource(
                self.config.youtube_api_key,
                self.config.youtube_queries
            ))
            logger.info(f"Initialized YouTubeSource with {len(self.config.youtube_queries)} queries")
        
        # Letterboxd (if configured)
        if self.config.letterboxd_usernames:
            self.sources.append(LetterboxdSource(self.config.letterboxd_usernames))
            logger.info(f"Initialized LetterboxdSource with {len(self.config.letterboxd_usernames)} users")
    
    def collect(self) -> list[Pebble]:
        """Collect pebbles from all sources."""
        all_pebbles = []
        
        for source in self.sources:
            try:
                pebbles = source.fetch()
                all_pebbles.extend(pebbles)
                logger.info(f"Collected {len(pebbles)} pebbles from {source.__class__.__name__}")
            except Exception as e:
                logger.error(f"Failed to collect from {source.__class__.__name__}: {e}")
        
        return all_pebbles
    
    def deliver(self, recipients: list[Recipient]) -> dict:
        """
        Deliver pebbles to recipients.
        
        Returns:
            Dict with delivery stats: {recipient_name: count_delivered}
        """
        stats = {}
        pebbles = self.collect()
        
        for recipient in recipients:
            delivered_count = self._deliver_to_recipient(recipient, pebbles)
            stats[recipient.name] = delivered_count
        
        return stats
    
    def _deliver_to_recipient(self, recipient: Recipient, pebbles: list[Pebble]) -> int:
        """Deliver matching pebbles to a single recipient."""
        # Check how many already delivered today
        delivered_today = self.storage.delivered_today(recipient.name)
        remaining_quota = recipient.max_daily_pebbles - delivered_today
        
        if remaining_quota <= 0:
            logger.info(f"Daily quota reached for {recipient.name}")
            return 0
        
        # Find matches with scores
        matches = []
        for pebble in pebbles:
            for interest in recipient.interests:
                if self.matcher.is_match(pebble, interest):
                    score = self.matcher.score(pebble, interest)
                    matches.append((pebble, interest, score))
                    break  # Only match once per pebble
        
        # Sort by interest priority (high to low), then score (high to low)
        matches.sort(key=lambda x: (x[1].priority, x[2]), reverse=True)
        
        # Take only what's within quota
        matches = matches[:remaining_quota]
        
        # Deliver
        delivered = 0
        for pebble, interest, score in matches:
            try:
                self.storage.store_pebble(pebble, recipient.name, interest.name, score)
                # TODO: actual delivery via telegram/email/webhook
                logger.info(
                    f"Delivered '{pebble.title}' to {recipient.name} "
                    f"(interest: {interest.name}, priority: {interest.priority}, score: {score:.2f})"
                )
                delivered += 1
            except Exception as e:
                logger.error(f"Failed to deliver pebble to {recipient.name}: {e}")
        
        return delivered
    
    def close(self):
        """Clean up resources."""
        for source in self.sources:
            try:
                source.close()
            except Exception as e:
                logger.warning(f"Error closing {source.__class__.__name__}: {e}")"""Core Pebbles collection and delivery engine."""

import logging
from datetime import datetime
from typing import Optional

from pebbles.config import Config
from pebbles.matcher import InterestMatcher
from pebbles.models import Pebble, Recipient
from pebbles.sources import HackerNewsSource, RedditSource, RSSSource, YouTubeSource, LetterboxdSource
from pebbles.storage import Storage
from pebbles.delivery import DeliveryService

logger = logging.getLogger(__name__)


class PebblesEngine:
    """Main engine for collecting and delivering Pebbles."""
    
    def __init__(self, config: Config, storage: Storage, delivery: DeliveryService):
        self.config = config
        self.storage = storage
        self.delivery = delivery
        self.matcher = InterestMatcher(
            use_semantic=config.use_semantic_matching,
            semantic_threshold=config.semantic_threshold
        )
        self.sources = self._init_sources()
    
    def _init_sources(self):
        """Initialize all configured sources."""
        sources = []
        
        # Always include HackerNews if configured
        if self.config.hackernews_num_items > 0:
            sources.append(HackerNewsSource(self.config.hackernews_num_items))
        
        # Reddit
        if self.config.reddit_subreddits:
            sources.append(RedditSource(self.config.reddit_subreddits))
        
        # RSS
        if self.config.rss_feeds:
            sources.append(RSSSource(self.config.rss_feeds))
        
        # YouTube
        if self.config.youtube_queries and self.config.youtube_api_key:
            sources.append(YouTubeSource(
                self.config.youtube_queries,
                self.config.youtube_api_key
            ))
        
        # Letterboxd
        if self.config.letterboxd_usernames:
            sources.append(LetterboxdSource(self.config.letterboxd_usernames))
        
        logger.info(f"Initialized {len(sources)} sources")
        return sources
    
    def run_once(self):
        """Run one collection and delivery cycle."""
        logger.info("Starting Pebbles collection cycle")
        
        # Fetch new pebbles
        pebbles = self._fetch_pebbles()
        logger.info(f"Fetched {len(pebbles)} total pebbles")
        
        # Match and deliver
        for recipient in self.config.recipients:
            self._deliver_to_recipient(recipient, pebbles)
        
        logger.info("Collection cycle complete")
    
    def _fetch_pebbles(self) -> list[Pebble]:
        """Fetch pebbles from all sources."""
        all_pebbles = []
        
        for source in self.sources:
            try:
                logger.info(f"Fetching from {source.__class__.__name__}")
                pebbles = source.fetch()
                all_pebbles.extend(pebbles)
                logger.info(f"Got {len(pebbles)} pebbles from {source.__class__.__name__}")
            except Exception as e:
                logger.error(f"Failed to fetch from {source.__class__.__name__}: {e}")
        
        return all_pebbles
    
    def _deliver_to_recipient(self, recipient: Recipient, pebbles: list[Pebble]):
        """Match and deliver pebbles to one recipient."""
        # Check daily limit
        delivered_today = self.storage.delivered_today(recipient.name)
        remaining = recipient.max_daily_pebbles - delivered_today
        
        if remaining <= 0:
            logger.info(f"Daily limit reached for {recipient.name}")
            return
        
        # Find matches and score them
        matches = []
        for pebble in pebbles:
            # Skip if already delivered
            if self.storage.was_delivered(pebble.url, recipient.name):
                continue
            
            # Check all interests
            for interest in recipient.interests:
                if self.matcher.is_match(pebble, interest):
                    score = self.matcher.score(pebble, interest)
                    matches.append((pebble, interest, score))
                    break  # Only match once per pebble
        
        if not matches:
            logger.info(f"No matches for {recipient.name}")
            return
        
        # Sort by interest priority (desc) then score (desc)
        matches.sort(key=lambda x: (x[1].priority, x[2]), reverse=True)
        
        # Cap at remaining daily limit
        matches = matches[:remaining]
        
        # Deliver
        for pebble, interest, score in matches:
            try:
                self.delivery.send(pebble, recipient, interest)
                self.storage.mark_delivered(pebble.url, recipient.name)
                logger.info(
                    f"Delivered '{pebble.title}' to {recipient.name} "
                    f"(interest: {interest.name}, priority: {interest.priority}, score: {score:.2f})"
                )
            except Exception as e:
                logger.error(f"Failed to deliver to {recipient.name}: {e}")
    
    def close(self):
        """Clean up resources."""
        for source in self.sources:
            try:
                source.close()
            except Exception as e:
                logger.error(f"Error closing {source.__class__.__name__}: {e}")