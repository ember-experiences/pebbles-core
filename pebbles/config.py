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
        return cls(**data)