"""
Hacker News source — fetches top/new/best stories.
"""

import time
from typing import List
import httpx
from pebbles.models import Pebble, SourceType


class HackerNewsSource:
    """Fetch stories from Hacker News API."""
    
    BASE_URL = "https://hacker-news.firebaseio.com/v0"
    RATE_LIMIT_DELAY = 1.0  # seconds between requests
    
    def __init__(self, max_stories: int = 30):
        self.max_stories = max_stories
        self.client = httpx.Client(timeout=10.0)
    
    def fetch(self, story_type: str = "top") -> List[Pebble]:
        """
        Fetch stories from HN.
        
        Args:
            story_type: "top", "new", or "best"
        
        Returns:
            List of Pebble objects
        """
        endpoint_map = {
            "top": f"{self.BASE_URL}/topstories.json",
            "new": f"{self.BASE_URL}/newstories.json",
            "best": f"{self.BASE_URL}/beststories.json"
        }
        
        if story_type not in endpoint_map:
            raise ValueError(f"Invalid story_type: {story_type}")
        
        # Fetch story IDs
        response = self.client.get(endpoint_map[story_type])
        response.raise_for_status()
        story_ids = response.json()[:self.max_stories]
        
        pebbles = []
        for story_id in story_ids:
            time.sleep(self.RATE_LIMIT_DELAY)
            story = self._fetch_story(story_id)
            if story:
                pebbles.append(story)
        
        return pebbles
    
    def _fetch_story(self, story_id: int) -> Pebble | None:
        """Fetch a single story by ID."""
        try:
            response = self.client.get(f"{self.BASE_URL}/item/{story_id}.json")
            response.raise_for_status()
            data = response.json()
            
            # Skip if no URL (Ask HN, Show HN without links, etc.)
            if not data.get("url"):
                return None
            
            return Pebble(
                url=data["url"],
                title=data.get("title", ""),
                summary=data.get("text", "")[:500] if data.get("text") else "",
                source=SourceType.HACKERNEWS,
                metadata={
                    "hn_id": story_id,
                    "score": data.get("score", 0),
                    "comments": data.get("descendants", 0),
                    "author": data.get("by", "")
                }
            )
        except Exception as e:
            # Log but don't crash on individual story failures
            print(f"Failed to fetch HN story {story_id}: {e}")
            return None
    
    def close(self):
        """Close HTTP client."""
        self.client.close()