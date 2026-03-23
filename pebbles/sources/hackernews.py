"""Hacker News source for pebbles."""
import requests
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from pebbles.log import get_logger

logger = get_logger(__name__)


class HackerNewsSource:
    """Fetch top stories from Hacker News."""
    
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    
    def __init__(self, max_items: int = 30):
        """Initialize HN source.
        
        Args:
            max_items: Maximum number of top stories to fetch
        """
        self.max_items = max_items
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _fetch_with_retry(self, url: str) -> Any:
        """Fetch URL with retry logic.
        
        Args:
            url: URL to fetch
            
        Returns:
            Parsed JSON response
            
        Raises:
            requests.RequestException: If all retries fail
        """
        logger.debug(f"Fetching: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
        
    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch top stories from HN.
        
        Returns:
            List of story dicts with url, title, score, comments_url
        """
        try:
            # Get top story IDs
            top_ids = self._fetch_with_retry(f"{self.BASE_URL}/topstories.json")
            
            stories = []
            for story_id in top_ids[:self.max_items]:
                try:
                    story = self._fetch_with_retry(f"{self.BASE_URL}/item/{story_id}.json")
                    
                    # Skip if no URL (e.g. Ask HN posts)
                    if not story.get('url'):
                        continue
                        
                    stories.append({
                        'url': story['url'],
                        'title': story.get('title', 'Untitled'),
                        'score': story.get('score', 0),
                        'comments_url': f"https://news.ycombinator.com/item?id={story_id}"
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch story {story_id}: {e}")
                    continue
                    
            logger.info(f"Successfully fetched {len(stories)} HN stories")
            return stories
            
        except Exception as e:
            logger.error(f"Failed to fetch HN top stories: {e}", exc_info=True)
            return []