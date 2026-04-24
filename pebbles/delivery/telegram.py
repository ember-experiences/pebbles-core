"""Telegram delivery adapter — synchronous, implements engine's Delivery protocol."""

import asyncio
import logging
from typing import Any

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramDelivery:
    """Deliver pebble items to Telegram recipients.

    Implements the `Delivery` protocol from pebbles.engine:
        def deliver(item: dict, recipient: str) -> bool

    `recipient` is the chat_id as a string.
    """

    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)

    def deliver(self, item: dict[str, Any], recipient: str) -> bool:
        """Deliver a raw item dict to a Telegram recipient.

        Args:
            item: Raw item dict with at least 'title' and 'url'.
                  Optional: 'description', 'metadata' (dict with 'score', 'comments').
            recipient: Telegram chat_id as a string.

        Returns:
            True if delivery succeeded.
        """
        message = self._format_message(item)
        try:
            asyncio.run(self._send_async(recipient, message))
            return True
        except TelegramError as e:
            logger.error(f"Telegram delivery failed to {recipient}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected delivery error to {recipient}: {e}")
            return False

    async def _send_async(self, chat_id: str, message: str):
        """Perform the actual send — python-telegram-bot's Bot.send_message is async."""
        await self.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=False,
        )

    def _format_message(self, item: dict[str, Any]) -> str:
        """Format an item dict as a Telegram message."""
        title = item.get("title", "(untitled)")
        url = item.get("url", "")
        description = item.get("description", "")

        lines = [f"🪨 *{title}*"]

        if description:
            lines.append(f"\n{description}")

        if url:
            lines.append(f"\n[Read more]({url})")

        metadata = item.get("metadata") or {}
        if metadata:
            meta_parts = []
            if "score" in metadata:
                meta_parts.append(f"⬆️ {metadata['score']}")
            if "comments" in metadata:
                meta_parts.append(f"💬 {metadata['comments']}")
            if meta_parts:
                lines.append(f"\n_{' · '.join(meta_parts)}_")

        return "\n".join(lines)
