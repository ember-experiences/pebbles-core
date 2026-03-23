"""Storage backend for pebbles."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pebbles.models import Pebble


class PebbleStorage:
    """SQLite storage for pebbles and delivery history."""
    
    def __init__(self, db_path: str | Path):
        """Initialize storage."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Create tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pebbles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                description TEXT,
                source TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pebble_id INTEGER NOT NULL,
                recipient_name TEXT NOT NULL,
                interest_name TEXT NOT NULL,
                score REAL NOT NULL,
                delivered_at TEXT NOT NULL,
                FOREIGN KEY (pebble_id) REFERENCES pebbles (id)
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_deliveries_recipient 
            ON deliveries (recipient_name, delivered_at)
        """)
        
        self.conn.commit()
    
    def store_pebble(
        self,
        pebble: Pebble,
        recipient_name: str,
        interest_name: str,
        score: float
    ):
        """Store a pebble and its delivery record."""
        # Insert or ignore pebble
        cursor = self.conn.execute("""
            INSERT OR IGNORE INTO pebbles (title, url, description, source, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            pebble.title,
            pebble.url,
            pebble.description,
            pebble.source,
            pebble.timestamp.isoformat(),
            str(pebble.metadata)
        ))
        
        # Get pebble_id
        pebble_id = cursor.lastrowid
        if pebble_id == 0:
            # Already exists, fetch it
            cursor = self.conn.execute(
                "SELECT id FROM pebbles WHERE url = ?",
                (pebble.url,)
            )
            row = cursor.fetchone()
            if row:
                pebble_id = row[0]
        
        # Record delivery
        self.conn.execute("""
            INSERT INTO deliveries (pebble_id, recipient_name, interest_name, score, delivered_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pebble_id,
            recipient_name,
            interest_name,
            score,
            datetime.now().isoformat()
        ))
        
        self.conn.commit()
    
    def delivered_today(self, recipient_name: str) -> int:
        """Count pebbles delivered to recipient in last 24 hours."""
        cutoff = (datetime.now() - timedelta(days=1)).isoformat()
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM deliveries
            WHERE recipient_name = ? AND delivered_at > ?
        """, (recipient_name, cutoff))
        return cursor.fetchone()[0]
    
    def get_stats(self) -> dict:
        """Get delivery statistics."""
        # Total pebbles
        cursor = self.conn.execute("SELECT COUNT(*) FROM pebbles")
        total_pebbles = cursor.fetchone()[0]
        
        # Deliveries in last 24h
        cutoff = (datetime.now() - timedelta(days=1)).isoformat()
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM deliveries WHERE delivered_at > ?",
            (cutoff,)
        )
        recent_deliveries = cursor.fetchone()[0]
        
        # Top recipients (last 24h)
        cursor = self.conn.execute("""
            SELECT recipient_name, COUNT(*) as count
            FROM deliveries
            WHERE delivered_at > ?
            GROUP BY recipient_name
            ORDER BY count DESC
            LIMIT 5
        """, (cutoff,))
        top_recipients = [
            {"name": row[0], "count": row[1]}
            for row in cursor.fetchall()
        ]
        
        return {
            "total_pebbles": total_pebbles,
            "deliveries_24h": recent_deliveries,
            "top_recipients": top_recipients
        }
    
    def close(self):
        """Close database connection."""
        self.conn.close()"""Storage layer for tracking delivered Pebbles."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Storage:
    """Simple file-based storage for delivery tracking."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
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
        with open(self.db_path, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def mark_delivered(self, url: str, recipient: str):
        """Record that a pebble was delivered."""
        self.data["deliveries"].append({
            "url": url,
            "recipient": recipient,
            "timestamp": datetime.utcnow().isoformat()
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
        cutoff = datetime.utcnow() - timedelta(days=1)
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
        
        # Count by recipient
        by_recipient = {}
        for delivery in self.data["deliveries"]:
            recipient = delivery["recipient"]
            by_recipient[recipient] = by_recipient.get(recipient, 0) + 1
        
        # Top 5 recipients
        top_recipients = sorted(
            by_recipient.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Last 24h
        cutoff = datetime.utcnow() - timedelta(days=1)
        last_24h = sum(
            1 for d in self.data["deliveries"]
            if datetime.fromisoformat(d["timestamp"]) > cutoff
        )
        
        return {
            "total_deliveries": total,
            "last_24h": last_24h,
            "top_recipients": top_recipients
        }