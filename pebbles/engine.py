"""Pebble distribution engine.

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
        self.delivery.close()