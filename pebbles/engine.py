"""
Pebble engine — orchestrate fetch → match → deliver pipeline.
"""

import asyncio
from typing import List
from pebbles.models import Pebble, Recipient
from pebbles.config import Settings
from pebbles.sources import HackerNewsSource
from pebbles.delivery import TelegramDelivery
from pebbles.storage import PebbleStorage


class PebbleEngine:
    """Core orchestrator for the pebble pipeline."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = PebbleStorage(settings.storage_path)
        self.delivery = TelegramDelivery(settings.telegram_bot_token)
    
    async def run(self):
        """Execute one full cycle: fetch → match → deliver."""
        print("🪨 Pebble engine starting...")
        
        # 1. Fetch pebbles from sources
        pebbles = self._fetch_pebbles()
        print(f"📥 Fetched {len(pebbles)} pebbles")
        
        # 2. Match pebbles to recipients based on interests
        matches = self._match_interests(pebbles)
        print(f"🎯 Matched {len(matches)} pebble-recipient pairs")
        
        # 3. Filter out already-delivered
        new_matches = self._filter_delivered(matches)
        print(f"✨ {len(new_matches)} new (undelivered) matches")
        
        if not new_matches:
            print("✅ No new pebbles to deliver")
            return
        
        # 4. Deliver
        sent_count = await self.delivery.send_batch(new_matches)
        print(f"📤 Delivered {sent_count}/{len(new_matches)} pebbles")
        
        # 5. Mark as delivered
        for pebble, recipient in new_matches:
            self.storage.mark_delivered(pebble.url, recipient.name)
        
        print("✅ Pebble run complete")
    
    def _fetch_pebbles(self) -> List[Pebble]:
        """Fetch pebbles from all configured sources."""
        pebbles = []
        
        # For now, just HN. Add more sources here as they're built.
        hn_source = HackerNewsSource(max_stories=30)
        try:
            pebbles.extend(hn_source.fetch("top"))
        finally:
            hn_source.close()
        
        return pebbles
    
    def _match_interests(self, pebbles: List[Pebble]) -> List[tuple[Pebble, Recipient]]:
        """Match pebbles to recipients based on interest keywords."""
        matches = []
        
        for recipient in self.settings.recipients:
            for pebble in pebbles:
                if self._is_match(pebble, recipient):
                    matches.append((pebble, recipient))
        
        return matches
    
    def _is_match(self, pebble: Pebble, recipient: Recipient) -> bool:
        """Check if a pebble matches a recipient's interests."""
        # Combine title + summary for matching
        text = f"{pebble.title} {pebble.summary}".lower()
        
        # Check if any interest keyword appears in the text
        return any(interest.lower() in text for interest in recipient.interests)
    
    def _filter_delivered(self, matches: List[tuple[Pebble, Recipient]]) -> List[tuple[Pebble, Recipient]]:
        """Remove pebbles that have already been delivered to these recipients."""
        return [
            (pebble, recipient)
            for pebble, recipient in matches
            if not self.storage.has_delivered(pebble.url, recipient.name)
        ]