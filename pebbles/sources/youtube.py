"""YouTube source for Pebbles.

Fetches videos using YouTube Data API v3.
Requires API key.
"""

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from pebbles.log import get_logger
from pebbles.models import Pebble

logger = get_logger(__name__)


class YouTubeSource:
    """Fetch pebbles from YouTube searches or channels."""
    
    def __init__(self, api_key: str | None, queries: list[str]):
        """Initialize with API key and search queries or channel IDs."""
        self.api_key = api_key
        self.queries = queries
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch(self) -> list[Pebble]:
        """Fetch recent videos from all configured queries."""
        if not self.api_key:
            logger.warning("YouTube API key not configured, skipping")
            return []
        
        pebbles = []
        
        for query in self.queries:
            try:
                logger.info(f"Searching YouTube for: {query}")
                
                url = "https://www.googleapis.com/youtube/v3/search"
                params = {
                    'key': self.api_key,
                    'q': query,
                    'part': 'snippet',
                    'type': 'video',
                    'maxResults': 10,
                    'order': 'date'
                }
                
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                items = data.get('items', [])
                
                for item in items:
                    snippet = item.get('snippet', {})
                    video_id = item.get('id', {}).get('videoId')
                    
                    if not video_id:
                        continue
                    
                    content = snippet.get('title', '')
                    description = snippet.get('description', '')
                    if description:
                        content = f"{content}\n\n{description}"
                    
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    pebbles.append(Pebble(
                        content=content,
                        url=video_url,
                        source=f"youtube:{query}"
                    ))
                
                logger.info(f"Fetched {len(items)} videos for query: {query}")
                
            except Exception as e:
                logger.error(f"Failed to fetch YouTube results for '{query}': {e}")
                continue
        
        return pebbles
    
    def close(self):
        """No cleanup needed for YouTube source."""
        pass