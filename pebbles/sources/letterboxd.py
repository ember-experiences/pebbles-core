"""Letterboxd source for Pebbles.

Fetches film reviews from user RSS feeds.
No scraping, RSS only.
"""

import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential
from pebbles.log import get_logger
from pebbles.models import Pebble

logger = get_logger(__name__)


class LetterboxdSource:
    """Fetch pebbles from Letterboxd user review feeds."""
    
    def __init__(self, usernames: list[str]):
        """Initialize with list of Letterboxd usernames."""
        self.usernames = usernames
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch(self) -> list[Pebble]:
        """Fetch recent reviews from all configured users."""
        pebbles = []
        
        for username in self.usernames:
            try:
                feed_url = f"https://letterboxd.com/{username}/rss/"
                logger.info(f"Fetching Letterboxd feed for {username}")
                
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:
                    logger.warning(f"Feed may be malformed for user: {username}")
                
                for entry in feed.entries[:10]:  # Limit to 10 most recent
                    # Letterboxd RSS entries contain film reviews
                    content = entry.get('title', '')
                    summary = entry.get('summary', '')
                    if summary:
                        content = f"{content}\n\n{summary}"
                    
                    url = entry.get('link', f"https://letterboxd.com/{username}/")
                    
                    pebbles.append(Pebble(
                        content=content,
                        url=url,
                        source=f"letterboxd:{username}"
                    ))
                
                logger.info(f"Fetched {len(feed.entries)} reviews from {username}")
                
            except Exception as e:
                logger.error(f"Failed to fetch Letterboxd feed for {username}: {e}")
                continue
        
        return pebbles
    
    def close(self):
        """No cleanup needed for Letterboxd source."""
        pass