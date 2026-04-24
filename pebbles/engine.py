"""Core pebble discovery and delivery engine."""
from typing import Protocol, List, Dict, Any

from pebbles.storage import Storage
from pebbles.log import get_logger

logger = get_logger(__name__)


class Source(Protocol):
    """Protocol for pebble sources."""

    def fetch(self) -> List[Dict[str, Any]]:
        """Fetch raw items from source.

        Returns:
            List of raw item dicts with at least 'url' and 'title'
        """
        ...


class Matcher(Protocol):
    """Protocol for interest matchers."""

    def match(self, item: Dict[str, Any]) -> bool:
        """Check if item matches user interests."""
        ...


class Filter(Protocol):
    """Protocol for content filters."""

    def filter(self, item: Dict[str, Any]) -> bool:
        """Check if item should be kept (True) or dropped (False)."""
        ...


class Delivery(Protocol):
    """Protocol for delivery adapters."""

    def deliver(self, item: Dict[str, Any], recipient: str) -> bool:
        """Deliver pebble to recipient. Returns True if delivery succeeded."""
        ...


class Engine:
    """Pebble discovery and delivery engine."""

    def __init__(
        self,
        sources: List[Source],
        matcher: Matcher,
        filter: Filter,
        delivery: Delivery,
        recipient: str,
        storage: Storage,
    ):
        self.sources = sources
        self.matcher = matcher
        self.filter = filter
        self.delivery = delivery
        self.recipient = recipient
        self.storage = storage

    def run(self) -> int:
        """Run one discovery cycle.

        Returns:
            Number of pebbles delivered
        """
        delivered_count = 0

        for source in self.sources:
            try:
                logger.info(f"Fetching from source: {source.__class__.__name__}")
                items = source.fetch()
                logger.info(f"Fetched {len(items)} items from {source.__class__.__name__}")

                for item in items:
                    url = item.get("url")
                    if not url:
                        logger.warning(f"Item missing URL, skipping: {item}")
                        continue

                    if self.storage.was_delivered(url, self.recipient):
                        continue

                    if not self.matcher.match(item):
                        continue

                    if not self.filter.filter(item):
                        logger.info(f"Item filtered: {item.get('title', url)}")
                        continue

                    if self.delivery.deliver(item, self.recipient):
                        self.storage.mark_delivered(url, self.recipient)
                        delivered_count += 1
                        logger.info(f"Delivered: {item.get('title', url)} to {self.recipient}")
                    else:
                        logger.error(f"Delivery failed: {item.get('title', url)}")

            except Exception as e:
                logger.error(f"Source {source.__class__.__name__} failed: {e}", exc_info=True)
                continue

        logger.info(f"Discovery cycle complete. Delivered {delivered_count} pebbles.")
        return delivered_count
