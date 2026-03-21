"""Configuration management for Pebbles."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pebbles.models import Recipient


class Settings(BaseSettings):
    """Pebbles configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PEBBLES_",
        case_sensitive=False,
    )
    
    # Core settings
    config_dir: Path = Field(default=Path.home() / ".config" / "pebbles")
    data_dir: Path = Field(default=Path.home() / ".local" / "share" / "pebbles")
    log_level: str = Field(default="INFO")
    
    # API keys
    anthropic_api_key: str = Field(description="Anthropic API key for context generation")
    
    # Redis (for deduplication)
    redis_url: str = Field(default="redis://localhost:6379/0")
    
    # Telegram (optional)
    telegram_bot_token: Optional[str] = Field(default=None)
    
    # Email (optional)
    smtp_host: Optional[str] = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    smtp_from: Optional[str] = Field(default=None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def recipients_file(self) -> Path:
        """Path to recipients config file."""
        return self.config_dir / "recipients.yaml"
    
    def load_recipients(self) -> list[Recipient]:
        """Load recipients from YAML config."""
        import yaml
        
        if not self.recipients_file.exists():
            return []
        
        with open(self.recipients_file) as f:
            data = yaml.safe_load(f)
        
        if not data or "recipients" not in data:
            return []
        
        return [Recipient(**r) for r in data["recipients"]]
    
    def save_recipients(self, recipients: list[Recipient]) -> None:
        """Save recipients to YAML config."""
        import yaml
        
        data = {"recipients": [r.model_dump(mode="json") for r in recipients]}
        
        with open(self.recipients_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)