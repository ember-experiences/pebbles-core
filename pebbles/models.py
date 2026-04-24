"""Core data models for pebbles."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class Pebble(BaseModel):
    """A single pebble - a content item from a source."""

    title: str
    url: str
    description: str = ""
    source: str
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict = Field(default_factory=dict)


class Interest(BaseModel):
    """An interest profile for matching content."""

    model_config = ConfigDict(populate_by_name=True)  # Allow both 'exclude' and 'negative_keywords'

    name: str
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list, alias="exclude")
    priority: int = Field(default=1, ge=1, le=3)  # 1=normal, 2=high, 3=must-have

    def matches(self, text: str) -> bool:
        """Check if text matches this interest (keyword mode only)."""
        text_lower = text.lower()

        for neg in self.negative_keywords:
            if neg.lower() in text_lower:
                return False

        for tag in self.tags:
            if tag.lower() in text_lower:
                return True

        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                return True

        return False


class Recipient(BaseModel):
    """A recipient who receives pebbles."""

    name: str
    interests: list[Interest]
    delivery_method: str = "telegram"  # telegram, email, webhook
    delivery_address: str  # chat_id, email, url
    max_daily_pebbles: int = 10
    metadata: dict = Field(default_factory=dict)
