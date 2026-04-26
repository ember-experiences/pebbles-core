"""Storage layer for tracking delivered Pebbles.

v0.2 introduces `pebbles.core.storage.Storage` as a Protocol. The concrete
JSON-file impl in this module is renamed `JsonStorage`. The name `Storage`
is preserved as an alias to `JsonStorage` so v0.1.0 code that imports
`from pebbles.storage import Storage` keeps working.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class JsonStorage:
    """Simple file-based storage for delivery tracking."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        """Load delivery history from disk."""
        if self.db_path.exists():
            with open(self.db_path) as f:
                self.data = json.load(f)
        else:
            self.data = {"deliveries": []}

    def _save(self):
        """Save delivery history to disk."""
        with open(self.db_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def mark_delivered(self, url: str, recipient: str):
        """Record that a pebble was delivered."""
        self.data["deliveries"].append({
            "url": url,
            "recipient": recipient,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save()

    def was_delivered(self, url: str, recipient: str) -> bool:
        """Check if a pebble was already delivered to a recipient."""
        for delivery in self.data["deliveries"]:
            if delivery["url"] == url and delivery["recipient"] == recipient:
                return True
        return False

    def delivered_today(self, recipient: str) -> int:
        """Count how many pebbles were delivered to recipient in last 24h."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        count = 0
        for delivery in self.data["deliveries"]:
            if delivery["recipient"] == recipient:
                ts = datetime.fromisoformat(delivery["timestamp"])
                if ts > cutoff:
                    count += 1
        return count

    def get_stats(self) -> dict:
        """Get delivery statistics."""
        total = len(self.data["deliveries"])

        by_recipient: dict[str, int] = {}
        for delivery in self.data["deliveries"]:
            recipient = delivery["recipient"]
            by_recipient[recipient] = by_recipient.get(recipient, 0) + 1

        top_recipients = sorted(
            by_recipient.items(), key=lambda x: x[1], reverse=True
        )[:5]

        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        last_24h = sum(
            1
            for d in self.data["deliveries"]
            if datetime.fromisoformat(d["timestamp"]) > cutoff
        )

        return {
            "total_deliveries": total,
            "last_24h": last_24h,
            "top_recipients": top_recipients,
        }


# Backwards-compat alias for v0.1.0 callers.
# `from pebbles.storage import Storage` continues to work.
# New code should prefer `from pebbles.storage import JsonStorage` for clarity,
# or `from pebbles.core.storage import Storage` for the Protocol.
Storage = JsonStorage
