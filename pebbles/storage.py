"""
Pebble storage — track delivered pebbles to prevent duplicates.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional


class PebbleStorage:
    """SQLite-backed deduplication tracker."""
    
    def __init__(self, db_path: str | Path = "pebbles.db"):
        self.db_path = Path(db_path)
        self._init_db()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS delivered_pebbles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    recipient_name TEXT NOT NULL,
                    delivered_at TEXT NOT NULL,
                    UNIQUE(url, recipient_name)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_delivered_url_recipient 
                ON delivered_pebbles(url, recipient_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_delivered_at 
                ON delivered_pebbles(delivered_at)
            """)
            conn.commit()
    
    def has_delivered(self, url: str, recipient_name: str) -> bool:
        """Check if this URL has been delivered to this recipient."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM delivered_pebbles WHERE url = ? AND recipient_name = ? LIMIT 1",
                (url, recipient_name)
            )
            return cursor.fetchone() is not None
    
    def mark_delivered(self, url: str, recipient_name: str) -> bool:
        """
        Mark a URL as delivered to a recipient.
        
        Returns:
            True if newly marked, False if already existed
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO delivered_pebbles (url, recipient_name, delivered_at) VALUES (?, ?, ?)",
                    (url, recipient_name, datetime.utcnow().isoformat())
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            # Already delivered
            return False
    
    def cleanup_old(self, days: int = 30):
        """Remove delivery records older than N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM delivered_pebbles WHERE delivered_at < ?", (cutoff,))
            conn.commit()