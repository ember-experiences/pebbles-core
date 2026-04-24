"""ContextBridge: injects RecentContext into prompts before LLM calls.

This is the thing that would have prevented the Robert/surf-photo failure.
Wrap any incoming message through `enrich_message` before sending to Claude,
and the relevant recent context gets prepended automatically.

Example — what would have happened with this in place:

    # During drive-home conversation:
    bridge.record_from_conversation(
        text="Robert texted, he just got out of the water at Doheny after dawn patrol",
        session_id="drive-home-voice",
    )

    # 20 minutes later, photo arrives from Robert:
    enriched = bridge.enrich_message(
        message="[photo: robert on a wave]",
        sender_entities=["robert"],
    )
    # enriched now contains:
    #   [Recent context — 18 min ago, from drive-home-voice]
    #   Robert just finished a dawn patrol surf session at Doheny.
    #
    #   [photo: robert on a wave]
"""

from pebbles.recent_context import RecentContextStore
from pebbles.entity_extract import extract_entities_fast
from typing import Optional
import asyncio


class ContextBridge:
    def __init__(self, store: Optional[RecentContextStore] = None, api_key: Optional[str] = None):
        self.store = store or RecentContextStore()
        self.api_key = api_key

    def record(
        self,
        entities: list[str],
        summary: str,
        session_id: str,
        ttl_minutes: int = 240,
    ) -> None:
        """Explicitly record a context entry with known entities."""
        self.store.write(
            entities=entities,
            summary=summary,
            source_session=session_id,
            ttl_minutes=ttl_minutes,
        )

    def record_from_text(
        self,
        text: str,
        summary: str,
        session_id: str,
        ttl_minutes: int = 240,
    ) -> list[str]:
        """Extract entities from text automatically, then record.

        Returns the extracted entities so the caller can verify/log them.
        """
        entities = extract_entities_fast(text)
        if entities:
            self.store.write(
                entities=entities,
                summary=summary,
                source_session=session_id,
                ttl_minutes=ttl_minutes,
            )
        return entities

    def enrich_message(
        self,
        message: str,
        sender_entities: Optional[list[str]] = None,
    ) -> str:
        """Prepend relevant recent context to an incoming message.

        Extracts entities from message text + any known sender entities,
        queries the store, and prepends matching context if found.

        Returns the enriched message string ready to pass to the LLM.
        """
        # Combine auto-extracted entities with any explicitly passed sender entities
        message_entities = extract_entities_fast(message)
        all_entities = list(set(message_entities + (sender_entities or [])))

        context_block = self.store.build_context_block(all_entities)

        if not context_block:
            return message

        return f"{context_block}\n\n---\n\n{message}"

    async def enrich_message_rich(
        self,
        message: str,
        sender_entities: Optional[list[str]] = None,
    ) -> str:
        """Same as enrich_message but uses Claude for entity extraction.

        Useful when the message text is ambiguous (e.g. 'he sent a photo').
        Requires api_key to be set on the bridge.
        """
        if not self.api_key:
            return self.enrich_message(message, sender_entities)

        from pebbles.entity_extract import extract_entities_rich
        message_entities = await extract_entities_rich(message, self.api_key)
        all_entities = list(set(message_entities + (sender_entities or [])))

        context_block = self.store.build_context_block(all_entities)

        if not context_block:
            return message

        return f"{context_block}\n\n---\n\n{message}"
