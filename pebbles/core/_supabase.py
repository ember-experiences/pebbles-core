"""Supabase-backed reference impls.

Behind the [supabase] extra. Import via:
    from pebbles.core._supabase import SupabaseQueue, SupabaseStorage, SupabaseMetrics

Schema expected (apply via your own migrations; this module does not create tables):

    CREATE TABLE <queue_table> (
        id TEXT PRIMARY KEY,
        principal_id TEXT NOT NULL,
        status TEXT NOT NULL,
        payload JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        -- plus whatever extra columns your transition() calls populate
    );

    CREATE TABLE <metrics_table> (
        id BIGSERIAL PRIMARY KEY,
        principal_id TEXT NOT NULL,
        metric_type TEXT NOT NULL,
        metric_value NUMERIC,
        metadata JSONB,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE <deliveries_table> (
        id BIGSERIAL PRIMARY KEY,
        url TEXT NOT NULL,
        recipient TEXT NOT NULL,
        delivered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from pebbles.core.queue import (
    InvalidTransitionError,
    QueueStatus,
    VALID_TRANSITIONS,
)

logger = logging.getLogger(__name__)


def _require_supabase():
    """Lazy-import supabase client. Raise helpful error if extra not installed."""
    try:
        from supabase import create_client, Client
        return create_client, Client
    except ImportError as e:
        raise ImportError(
            "Supabase impls require `supabase` package. "
            "Install: pip install pebbles-core[supabase]"
        ) from e


class SupabaseQueue:
    """Queue impl backed by a Supabase table.

    Constructor takes the table name so Presence (`presence_queue`) and
    Scout (`scout_candidates`) can use the same impl with different tables.
    """

    def __init__(self, supabase_client, table: str = "queue"):
        self.client = supabase_client
        self.table = table

    def enqueue(self, principal_id: str, payload: dict) -> str:
        item_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "id": item_id,
            "principal_id": principal_id,
            "status": QueueStatus.PENDING.value,
            "payload": payload,
            "created_at": now,
            "updated_at": now,
        }
        self.client.table(self.table).insert(row).execute()
        return item_id

    def get(self, item_id: str) -> Optional[dict]:
        r = self.client.table(self.table).select("*").eq("id", item_id).execute()
        return r.data[0] if r.data else None

    def transition(self, item_id: str, to_status: QueueStatus, **fields) -> bool:
        item = self.get(item_id)
        if item is None:
            raise KeyError(f"Queue item not found: {item_id}")

        current = QueueStatus(item["status"])
        if to_status not in VALID_TRANSITIONS[current]:
            raise InvalidTransitionError(current, to_status, item_id)

        update = {
            "status": to_status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        self.client.table(self.table).update(update).eq("id", item_id).execute()
        return True

    def list(self, principal_id, status=None, limit=50) -> list[dict]:
        q = self.client.table(self.table).select("*").eq("principal_id", principal_id)
        if status is not None:
            q = q.eq("status", status.value)
        r = q.order("created_at", desc=True).limit(limit).execute()
        return r.data or []


class SupabaseMetrics:
    """MetricsEmitter impl backed by a Supabase table."""

    def __init__(self, supabase_client, table: str = "metrics"):
        self.client = supabase_client
        self.table = table

    def emit(self, principal_id, metric_type, value=None, metadata=None):
        row = {
            "principal_id": principal_id,
            "metric_type": metric_type,
            "metric_value": value,
            "metadata": metadata or {},
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.client.table(self.table).insert(row).execute()
        except Exception as e:
            # Metrics emission shouldn't break callers. Log and move on.
            logger.error(f"Failed to emit metric to Supabase: {e}")


class SupabaseStorage:
    """Delivery-tracking storage impl backed by a Supabase table.

    Implements the v0.1 Storage Protocol (mark_delivered, was_delivered,
    delivered_today, get_stats). Caller creates the underlying table.
    """

    def __init__(self, supabase_client, table: str = "deliveries"):
        self.client = supabase_client
        self.table = table

    def mark_delivered(self, url: str, recipient: str) -> None:
        row = {
            "url": url,
            "recipient": recipient,
            "delivered_at": datetime.now(timezone.utc).isoformat(),
        }
        self.client.table(self.table).insert(row).execute()

    def was_delivered(self, url: str, recipient: str) -> bool:
        r = (
            self.client.table(self.table)
            .select("id")
            .eq("url", url)
            .eq("recipient", recipient)
            .limit(1)
            .execute()
        )
        return bool(r.data)

    def delivered_today(self, recipient: str) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        r = (
            self.client.table(self.table)
            .select("id", count="exact")
            .eq("recipient", recipient)
            .gte("delivered_at", cutoff)
            .execute()
        )
        return r.count or 0

    def get_stats(self) -> dict:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        total_r = self.client.table(self.table).select("id", count="exact").execute()
        total = total_r.count or 0

        recent_r = (
            self.client.table(self.table)
            .select("id", count="exact")
            .gte("delivered_at", cutoff)
            .execute()
        )
        last_24h = recent_r.count or 0

        # Top 5 recipients overall (pulls all rows; OK for moderate volumes,
        # consider a SQL view or RPC for high-volume deployments)
        rows_r = self.client.table(self.table).select("recipient").execute()
        by_recipient: dict[str, int] = {}
        for row in (rows_r.data or []):
            r = row.get("recipient", "")
            by_recipient[r] = by_recipient.get(r, 0) + 1
        top = sorted(by_recipient.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_deliveries": total,
            "last_24h": last_24h,
            "top_recipients": top,
        }
