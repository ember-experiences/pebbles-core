"""
Telegram delivery — send pebbles to Telegram chats.
"""

import asyncio
from typing import List
from telegram import Bot
from telegram.error import TelegramError
from pebbles.models import Pebble, Recipient


class TelegramDelivery:
    """Send pebbles to Telegram recipients."""
    
    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
    
    async def send(self, pebble: Pebble, recipient: Recipient) -> bool:
        """
        Send a single pebble to a recipient.
        
        Returns:
            True if sent successfully, False otherwise
        """
        message = self._format_message(pebble)
        
        try:
            await self.bot.send_message(
                chat_id=recipient.telegram_chat_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            return True
        except TelegramError as e:
            print(f"Failed to send pebble to {recipient.name}: {e}")
            return False
    
    async def send_batch(self, pebbles: List[tuple[Pebble, Recipient]]) -> int:
        """
        Send multiple pebbles.
        
        Args:
            pebbles: List of (pebble, recipient) tuples
        
        Returns:
            Number of successfully sent pebbles
        """
        tasks = [self.send(pebble, recipient) for pebble, recipient in pebbles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is True)
    
    def _format_message(self, pebble: Pebble) -> str:
        """Format a pebble as a Telegram message."""
        lines = [f"🪨 *{pebble.title}*"]
        
        if pebble.summary:
            lines.append(f"\n{pebble.summary}")
        
        lines.append(f"\n[Read more]({pebble.url})")
        
        # Add metadata if present
        if pebble.metadata:
            meta_parts = []
            if "score" in pebble.metadata:
                meta_parts.append(f"⬆️ {pebble.metadata['score']}")
            if "comments" in pebble.metadata:
                meta_parts.append(f"💬 {pebble.metadata['comments']}")
            if meta_parts:
                lines.append(f"\n_{' · '.join(meta_parts)}_")
        
        return "\n".join(lines)