"""Configuration management for Pebbles."""

from pathlib import Path
from pydantic import BaseModel, Field
import tomli


class Config(BaseModel):
    """Pebbles configuration model."""
    
    # Twilio credentials
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    
    # Recipients
    recipients: list[str] = Field(default_factory=list)
    
    # Reddit source (opt-in)
    reddit_subreddits: list[str] = Field(default_factory=list)
    
    # RSS source (opt-in)
    rss_feeds: list[str] = Field(default_factory=list)
    
    # YouTube source (opt-in, requires API key)
    youtube_api_key: str | None = None
    youtube_queries: list[str] = Field(default_factory=list)
    
    # Letterboxd source (opt-in)
    letterboxd_usernames: list[str] = Field(default_factory=list)
    
    @classmethod
    def load(cls, path: Path = Path("pebbles.toml")) -> "Config":
        """Load configuration from TOML file."""
        with open(path, "rb") as f:
            data = tomli.load(f)
        return cls(**data)"""Configuration for Pebbles engine."""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field


class PebbleConfig(BaseModel):
    """Configuration for pebble collection and delivery."""
    
    # Storage
    db_path: Path = Field(
        default=Path.home() / ".pebbles" / "pebbles.db",
        description="Path to SQLite database"
    )
    
    # HackerNews (legacy - keeping for backward compat)
    hackernews_enabled: bool = Field(
        default=True,
        description="Enable HackerNews source"
    )
    
    # Reddit
    reddit_subreddits: Optional[List[str]] = Field(
        default=None,
        description="List of subreddit names to follow (e.g., ['surfing', 'climbing'])"
    )
    
    # RSS
    rss_feeds: Optional[List[str]] = Field(
        default=None,
        description="List of RSS/Atom feed URLs"
    )
    
    # YouTube
    youtube_api_key: Optional[str] = Field(
        default=None,
        description="YouTube Data API v3 key"
    )
    youtube_queries: Optional[List[str]] = Field(
        default=None,
        description="List of search queries or channel IDs"
    )
    
    # Letterboxd
    letterboxd_usernames: Optional[List[str]] = Field(
        default=None,
        description="List of Letterboxd usernames to follow"
    )
    
    # Collection timing
    collection_interval_minutes: int = Field(
        default=60,
        description="Minutes between collection cycles"
    )
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True"""Configuration for pebbles."""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class PebblesConfig(BaseModel):
    """Configuration for the pebbles engine."""
    
    # Storage
    db_path: Path = Field(default=Path.home() / ".pebbles" / "pebbles.db")
    
    # Sources
    reddit_subreddits: list[str] = Field(default_factory=list)
    rss_feeds: list[str] = Field(default_factory=list)
    youtube_api_key: Optional[str] = None
    youtube_queries: list[str] = Field(default_factory=list)
    letterboxd_usernames: list[str] = Field(default_factory=list)
    
    # Matching
    use_semantic_matching: bool = False
    semantic_threshold: float = 0.35
    
    # Delivery
    telegram_bot_token: Optional[str] = None
    
    class Config:
        env_prefix = "PEBBLES_""""Configuration management for Pebbles."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel

from pebbles.models import Recipient


class Config(BaseModel):
    """Main configuration for Pebbles engine."""
    
    # Sources
    hackernews_num_items: int = 30
    reddit_subreddits: list[str] = []
    rss_feeds: list[str] = []
    youtube_api_key: Optional[str] = None
    youtube_queries: list[str] = []
    letterboxd_usernames: list[str] = []
    
    # Matching
    use_semantic_matching: bool = False
    semantic_threshold: float = 0.35
    
    # Delivery
    recipients: list[Recipient]
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_from_number: str
    
    # Storage
    db_path: Path = Path("~/.pebbles/pebbles.db").expanduser()
    
    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)