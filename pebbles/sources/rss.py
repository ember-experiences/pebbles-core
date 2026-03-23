"""RSS feed source for Pebbles.

Fetches entries from configured RSS/Atom feeds using feedparser.
"""

import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential
from pebbles.log import get_logger
from pebbles.models import Pebble

logger = get_logger(__name__)


class RSSSource:
    """Fetch pebbles from RSS/Atom feeds."""
    
    def __init__(self, feed_urls: list[str]):
        """Initialize with list of feed URLs."""
        self.feed_urls = feed_urls
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch(self) -> list[Pebble]:
        """Fetch recent entries from all configured feeds."""
        pebbles = []
        
        for feed_url in self.feed_urls:
            try:
                logger.info(f"Fetching RSS feed: {feed_url}")
                
                feed = feedparser.parse(feed_url)
                
                if feed.bozo:  # feedparser's way of saying "this feed has issues"
                    logger.warning(f"Feed may be malformed: {feed_url}")
                
                for entry in feed.entries[:10]:  # Limit to 10 most recent
                    content = entry.get('title', '')
                    summary = entry.get('summary', '')
                    if summary:
                        content = f"{content}\n\n{summary}"
                    
                    url = entry.get('link', feed_url)
                    
                    pebbles.append(Pebble(
                        content=content,
                        url=url,
                        source=f"rss:{feed.feed.get('title', feed_url)}"
                    ))
                
                logger.info(f"Fetched {len(feed.entries)} entries from {feed_url}")
                
            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {feed_url}: {e}")
                continue
        
        return pebbles
    
    def close(self):
        """No cleanup needed for RSS source."""
        pass