"""Configuration for pebbles."""

from pathlib import Path
from typing import Optional, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from pebbles.models import Recipient, Interest


class PebblesConfig(BaseModel):
    """Configuration for the pebbles engine.

    Loadable from YAML via `PebblesConfig.from_yaml(path)` (matches the
    shape documented in README.md) or constructed directly for testing.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Storage
    db_path: Path = Field(default_factory=lambda: Path.home() / ".pebbles" / "pebbles.db")

    # Recipients (populated from YAML `recipients:` list)
    recipients: list[Recipient] = Field(default_factory=list)

    # Sources
    hackernews_enabled: bool = False
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
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None

    @classmethod
    def from_yaml(cls, path: Path | str) -> "PebblesConfig":
        """Load configuration from a YAML file matching the README shape.

        Expands ${VAR} references against the current environment so secrets
        can live in env vars, not in the YAML file.
        """
        import os
        import re

        with open(path) as f:
            raw = f.read()

        # Expand ${VAR} to os.environ[VAR] (empty string if missing)
        raw = re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", lambda m: os.environ.get(m.group(1), ""), raw)

        data: dict[str, Any] = yaml.safe_load(raw) or {}
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "PebblesConfig":
        """Translate nested YAML shape to flat PebblesConfig + Recipient list."""
        kwargs: dict[str, Any] = {}

        # Recipients — translate telegram_id/email to delivery_method+delivery_address
        recipients_raw = data.get("recipients", [])
        recipients: list[Recipient] = []
        for r in recipients_raw:
            if "telegram_id" in r:
                delivery_method = "telegram"
                delivery_address = str(r["telegram_id"])
            elif "email" in r:
                delivery_method = "email"
                delivery_address = r["email"]
            else:
                raise ValueError(
                    f"Recipient '{r.get('name', '?')}' must have telegram_id or email"
                )

            interests = []
            for idx, i in enumerate(r.get("interests", [])):
                # Synthesize a name if not provided — YAML example in README uses
                # tag-first blobs without explicit names.
                if "name" not in i:
                    i = dict(i)
                    i["name"] = "_".join(i.get("tags", [])) or f"interest_{idx}"
                interests.append(Interest(**i))
            recipients.append(
                Recipient(
                    name=r["name"],
                    interests=interests,
                    delivery_method=delivery_method,
                    delivery_address=delivery_address,
                    max_daily_pebbles=r.get("max_daily_pebbles", 10),
                )
            )
        kwargs["recipients"] = recipients

        # Sources
        sources = data.get("sources", {})
        if "hackernews" in sources:
            kwargs["hackernews_enabled"] = sources["hackernews"].get("enabled", False)
        if "reddit" in sources and sources["reddit"].get("enabled"):
            kwargs["reddit_subreddits"] = sources["reddit"].get("subreddits", [])
        if "rss" in sources and sources["rss"].get("enabled"):
            kwargs["rss_feeds"] = sources["rss"].get("feeds", [])
        if "youtube" in sources and sources["youtube"].get("enabled"):
            kwargs["youtube_api_key"] = sources["youtube"].get("api_key")
            kwargs["youtube_queries"] = sources["youtube"].get("queries", [])
        if "letterboxd" in sources and sources["letterboxd"].get("enabled"):
            kwargs["letterboxd_usernames"] = sources["letterboxd"].get("usernames", [])

        # Delivery
        delivery = data.get("delivery", {})
        if "telegram" in delivery:
            kwargs["telegram_bot_token"] = delivery["telegram"].get("bot_token")
        if "email" in delivery:
            email_cfg = delivery["email"]
            kwargs["smtp_host"] = email_cfg.get("smtp_host")
            kwargs["smtp_port"] = email_cfg.get("smtp_port", 587)
            kwargs["smtp_user"] = email_cfg.get("smtp_user")
            kwargs["smtp_password"] = email_cfg.get("smtp_password")
            kwargs["smtp_from"] = email_cfg.get("smtp_from")

        # Matching
        matching = data.get("matching", {})
        kwargs["use_semantic_matching"] = matching.get("use_semantic_matching", False)
        kwargs["semantic_threshold"] = matching.get("semantic_threshold", 0.35)

        return cls(**kwargs)
