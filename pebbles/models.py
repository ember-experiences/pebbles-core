"""Core data models for Pebbles."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, HttpUrl


class SourceType(str, Enum):
    """Content source types."""
    HACKERNEWS = "hackernews"
    REDDIT = "reddit"
    LETTERBOXD = "letterboxd"
    YOUTUBE = "youtube"
    RSS = "rss"


class DeliveryMethod(str, Enum):
    """Delivery channel types."""
    TELEGRAM = "telegram"
    EMAIL = "email"


class Interest(BaseModel):
    """An interest profile for matching content."""
    tags: list[str] = Field(description="Interest tags")
    keywords: list[str] = Field(default_factory=list, description="Keyword matches")
    exclude: list[str] = Field(default_factory=list, description="Exclusion filters")
    
    def matches(self, content: str) -> bool:
        """Check if content matches this interest."""
        content_lower = content.lower()
        
        # Exclusions take priority
        if any(ex.lower() in content_lower for ex in self.exclude):
            return False
        
        # Require tag or keyword match
        tag_match = any(tag.lower() in content_lower for tag in self.tags)
        keyword_match = any(kw.lower() in content_lower for kw in self.keywords)
        
        return tag_match or keyword_match


class Recipient(BaseModel):
    """Pebbles recipient configuration."""
    id: str = Field(description="Unique identifier")
    name: str = Field(description="Display name")
    interests: list[Interest] = Field(description="Interest profiles")
    delivery_method: DeliveryMethod = Field(description="Delivery channel")
    delivery_address: str = Field(description="Telegram username or email")
    max_daily_pebbles: int = Field(default=3, description="Max pebbles per day")
    enabled: bool = Field(default=True, description="Monitoring active")


class Pebble(BaseModel):
    """A discovered content item."""
    id: str = Field(description="Unique identifier")
    source: SourceType = Field(description="Content source")
    url: HttpUrl = Field(description="Content URL")
    title: str = Field(description="Content title")
    description: Optional[str] = Field(default=None, description="Content description")
    matched_interest: str = Field(description="Triggering interest")
    context: str = Field(description="AI-generated context")
    discovered_at: datetime = Field(default_factory=datetime.now)
    delivered: bool = Field(default=False)
    delivered_at: Optional[datetime] = Field(default=None)
    recipient_id: str = Field(description="Recipient ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Source metadata")
    
    def delivery_message(self, sender_name: str = "Pebbles") -> str:
        """Format message for delivery."""
        return f"""🪨 {self.title}

{self.context}

{self.url}

— {sender_name}"""