"""Core data models for pebbles."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


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
    
    name: str
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list, alias="exclude")
    priority: int = Field(default=1, ge=1, le=3)  # 1=normal, 2=high, 3=must-have
    
    class Config:
        populate_by_name = True  # Allow both 'exclude' and 'negative_keywords'
    
    def matches(self, text: str) -> bool:
        """Check if text matches this interest (keyword mode only)."""
        text_lower = text.lower()
        
        # Check negative keywords first
        for neg in self.negative_keywords:
            if neg.lower() in text_lower:
                return False
        
        # Check tags
        for tag in self.tags:
            if tag.lower() in text_lower:
                return True
        
        # Check keywords
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
    metadata: dict = Field(default_factory=dict)"""Core Pebbles data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Pebble(BaseModel):
    """A single piece of content from a source."""
    
    title: str
    url: str
    content: Optional[str] = None
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def __hash__(self):
        return hash(self.url)
    
    def __eq__(self, other):
        if not isinstance(other, Pebble):
            return False
        return self.url == other.url


class Interest(BaseModel):
    """A topic or area of interest to match against."""
    
    name: str
    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list, alias="exclude")
    priority: int = 1  # 1=normal, 2=high, 3=must-have
    
    class Config:
        populate_by_name = True  # Allow both 'negative_keywords' and 'exclude'


class Recipient(BaseModel):
    """A person who receives matched Pebbles."""
    
    name: str
    phone: str
    interests: list[Interest]
    max_daily_pebbles: int = 10