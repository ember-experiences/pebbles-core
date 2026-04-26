"""MetricsEmitter Protocol + reference impls.

A structured event sink. Not a logger, not a tracer — emits timestamped
events that downstream stores (Supabase, log file, prometheus exporter, etc)
can persist. Used by Presence (presence_metrics) and Scout (scout_metrics).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


class MetricsEmitter(Protocol):
    """Protocol for emitting principal-scoped metric events."""

    def emit(
        self,
        principal_id: str,
        metric_type: str,
        value: float | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Record a metric event. Timestamp is added by the emitter."""
        ...


class InMemoryMetrics:
    """Reference impl. Keeps events in a list. For tests + dev."""

    def __init__(self):
        self.events: list[dict] = []

    def emit(self, principal_id, metric_type, value=None, metadata=None):
        self.events.append({
            "principal_id": principal_id,
            "metric_type": metric_type,
            "value": value,
            "metadata": metadata or {},
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        })

    def filter(self, principal_id: str | None = None, metric_type: str | None = None) -> list[dict]:
        """Convenience for tests: filter events by principal/type."""
        out = self.events
        if principal_id is not None:
            out = [e for e in out if e["principal_id"] == principal_id]
        if metric_type is not None:
            out = [e for e in out if e["metric_type"] == metric_type]
        return out


class JsonFileMetrics:
    """Append-only JSONL file. For long-running dev / single-machine deployments."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, principal_id, metric_type, value=None, metadata=None):
        event = {
            "principal_id": principal_id,
            "metric_type": metric_type,
            "value": value,
            "metadata": metadata or {},
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(event) + "\n")
