"""RecentContext: short-lived, entity-keyed context that bridges conversation sessions.

The problem this solves: Song learns Robert is surfing (session A). Robert sends a
photo 20 minutes later (session B). Session B has no knowledge of session A.

Solution: when you learn something time-sensitive about a person or place, write a
RecentContext entry keyed to those entities. Any new message referencing those entities
gets that context injected before the LLM responds.
"""

from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field
import json
from pathlib import Path


class RecentContextEntry(BaseModel):
    """A short-lived context fragment keyed to entities."""
    id: str
    entities: list[str] = Field(description="People, places, or things this context is about (lowercase)")
    summary: str = Field(description="What happened / what's relevant")
    source_session: str = Field(description="Where this context came from (e.g. 'drive-home-voice')")
    created_at: datetime = Field(default_factory=datetime.now)
    ttl_minutes: int = Field(default=240, description="How long this context stays live (default 4 hours)")

    @property
    def expires_at(self) -> datetime:
        return self.created_at + timedelta(minutes=self.ttl_minutes)

    @property
    def is_live(self) -> bool:
        return datetime.now() < self.expires_at

    @property
    def age_minutes(self) -> float:
        return (datetime.now() - self.created_at).total_seconds() / 60

    def relevance_score(self, query_entities: list[str]) -> float:
        """How relevant is this entry to a set of query entities?

        Combines entity overlap with recency — a 20-minute-old entry
        about Robert scores much higher than a 3-hour-old one.
        """
        query_lower = {e.lower() for e in query_entities}
        entry_lower = {e.lower() for e in self.entities}

        overlap = len(query_lower & entry_lower)
        if overlap == 0:
            return 0.0

        # Recency factor: full weight under 30 min, decays to 0.2 at TTL
        age_ratio = self.age_minutes / self.ttl_minutes
        recency = max(0.2, 1.0 - (age_ratio * 0.8))

        return overlap * recency


class RecentContextStore:
    """Persistent store for short-lived cross-session context.

    Backed by a JSON file so it survives process restarts (e.g. voice session ends,
    new chat session opens).

    Usage:
        store = RecentContextStore()

        # In the drive-home session, when we learn Robert is surfing:
        store.write(
            entities=["robert", "doheny"],
            summary="Robert is on a dawn patrol surf session at Doheny. Left ~5am,
                     probably finishing up around now.",
            source_session="drive-home-voice",
            ttl_minutes=180,
        )

        # Later, when Robert's photo arrives, before responding:
        context = store.query(entities=["robert"])
        # → injects "Robert is on a dawn patrol surf session at Doheny" into the prompt
    """

    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = store_path or (
            Path.home() / ".local" / "share" / "pebbles" / "recent_context.json"
        )
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[RecentContextEntry]:
        if not self.store_path.exists():
            return []
        with open(self.store_path) as f:
            raw = json.load(f)
        entries = [RecentContextEntry(**r) for r in raw]
        return [e for e in entries if e.is_live]

    def _save(self, entries: list[RecentContextEntry]) -> None:
        with open(self.store_path, "w") as f:
            json.dump([e.model_dump(mode="json") for e in entries], f, indent=2, default=str)

    def write(
        self,
        entities: list[str],
        summary: str,
        source_session: str,
        ttl_minutes: int = 240,
        entry_id: Optional[str] = None,
    ) -> RecentContextEntry:
        """Write a new context entry. Overwrites any existing entry with the same id."""
        import uuid
        entry = RecentContextEntry(
            id=entry_id or str(uuid.uuid4()),
            entities=[e.lower() for e in entities],
            summary=summary,
            source_session=source_session,
            ttl_minutes=ttl_minutes,
        )
        entries = self._load()
        # Replace if same id
        entries = [e for e in entries if e.id != entry.id]
        entries.append(entry)
        self._save(entries)
        return entry

    def query(self, entities: list[str], min_score: float = 0.1) -> list[RecentContextEntry]:
        """Return live entries relevant to these entities, sorted by relevance score."""
        entries = self._load()
        scored = [
            (e, e.relevance_score(entities))
            for e in entries
        ]
        relevant = [(e, s) for e, s in scored if s >= min_score]
        relevant.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in relevant]

    def build_context_block(self, entities: list[str]) -> Optional[str]:
        """Format relevant recent context for injection into a prompt.

        Returns None if nothing relevant exists.

        Example output:
            [Recent context — 18 min ago, from drive-home-voice]
            Robert is on a dawn patrol surf session at Doheny. Left ~5am.
        """
        entries = self.query(entities)
        if not entries:
            return None

        lines = []
        for entry in entries:
            age = int(entry.age_minutes)
            age_str = f"{age} min ago" if age < 60 else f"{age // 60}h {age % 60}m ago"
            lines.append(
                f"[Recent context — {age_str}, from {entry.source_session}]\n{entry.summary}"
            )

        return "\n\n".join(lines)

    def expire_all(self) -> int:
        """Remove expired entries. Returns count removed."""
        if not self.store_path.exists():
            return 0
        with open(self.store_path) as f:
            raw = json.load(f)
        all_entries = [RecentContextEntry(**r) for r in raw]
        live = [e for e in all_entries if e.is_live]
        self._save(live)
        return len(all_entries) - len(live)
