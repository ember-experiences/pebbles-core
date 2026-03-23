"""Reddit source for Pebbles.

Fetches recent posts from configured subreddits using Reddit's JSON API.
No authentication required.
"""

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from pebbles.log import get_logger
from pebbles.models import Pebble

logger = get_logger(__name__)


class RedditSource:
    """Fetch pebbles from Reddit subreddits."""
    
    def __init__(self, subreddits: list[str]):
        """Initialize with list of subreddit names (without r/)."""
        self.subreddits = subreddits
        self.headers = {
            'User-Agent': 'pebbles/1.0.0 (https://github.com/agent-embers/pebbles-core)'
        }
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch(self) -> list[Pebble]:
        """Fetch recent posts from all configured subreddits."""
        pebbles = []
        
        for subreddit in self.subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/new.json"
                logger.info(f"Fetching from r/{subreddit}")
                
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                posts = data.get('data', {}).get('children', [])
                
                for post_data in posts[:10]:  # Limit to 10 most recent
                    post = post_data.get('data', {})
                    
                    # Build content from title + selftext
                    content = post.get('title', '')
                    selftext = post.get('selftext', '')
                    if selftext:
                        content = f"{content}\n\n{selftext}"
                    
                    url = post.get('url', '')
                    if not url.startswith('http'):
                        url = f"https://reddit.com{url}"
                    
                    pebbles.append(Pebble(
                        content=content,
                        url=url,
                        source=f"reddit:r/{subreddit}"
                    ))
                
                logger.info(f"Fetched {len(posts)} posts from r/{subreddit}")
                
            except Exception as e:
                logger.error(f"Failed to fetch r/{subreddit}: {e}")
                continue
        
        return pebbles
    
    def close(self):
        """No cleanup needed for Reddit source."""
        pass