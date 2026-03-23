"""CLI entry point for pebbles."""
import click
import time
from pathlib import Path
from datetime import datetime, timedelta

from pebbles.engine import Engine
from pebbles.storage import Storage
from pebbles.sources.hackernews import HackerNewsSource
from pebbles.delivery.telegram import TelegramDelivery
from pebbles.log import get_logger

logger = get_logger(__name__)


class SimpleKeywordMatcher:
    """Simple keyword-based matcher."""
    
    def __init__(self, keywords: list[str]):
        self.keywords = [k.lower() for k in keywords]
        
    def match(self, item: dict) -> bool:
        """Check if item contains any keywords."""
        text = f"{item.get('title', '')} {item.get('url', '')}".lower()
        return any(kw in text for kw in self.keywords)


class NoOpFilter:
    """Pass-through filter that accepts everything."""
    
    def filter(self, item: dict) -> bool:
        """Always return True."""
        return True


@click.group()
def cli():
    """Pebbles — autonomous discovery and delivery."""
    pass


@cli.command()
@click.option('--keywords', default='ai,llm,claude,agent', help='Comma-separated keywords')
@click.option('--telegram-token', envvar='TELEGRAM_BOT_TOKEN', required=True)
@click.option('--telegram-chat', envvar='TELEGRAM_CHAT_ID', required=True)
@click.option('--loop', is_flag=True, help='Run continuously every 15 minutes')
def run(keywords, telegram_token, telegram_chat, loop):
    """Run pebble discovery."""
    db_path = Path.home() / '.pebbles' / 'pebbles.db'
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    storage = Storage(str(db_path))
    source = HackerNewsSource(max_items=30)
    matcher = SimpleKeywordMatcher(keywords.split(','))
    filter_obj = NoOpFilter()
    delivery = TelegramDelivery(telegram_token)
    
    engine = Engine(
        sources=[source],
        matcher=matcher,
        filter=filter_obj,
        delivery=delivery,
        recipient=telegram_chat,
        storage=storage
    )
    
    if loop:
        logger.info("Starting continuous loop (15 min interval)")
        while True:
            try:
                count = engine.run()
                logger.info(f"Loop iteration complete. Delivered {count} pebbles.")
            except Exception as e:
                logger.error(f"Loop iteration failed: {e}", exc_info=True)
            time.sleep(900)  # 15 minutes
    else:
        count = engine.run()
        logger.info(f"Single run complete. Delivered {count} pebbles.")


@cli.command()
def status():
    """Show pebble delivery statistics."""
    db_path = Path.home() / '.pebbles' / 'pebbles.db'
    
    if not db_path.exists():
        click.echo("No pebbles database found. Run 'pebbles run' first.")
        return
        
    storage = Storage(str(db_path))
    conn = storage.conn
    cursor = conn.cursor()
    
    # Total delivered
    cursor.execute("SELECT COUNT(*) FROM delivered")
    total = cursor.fetchone()[0]
    
    # Delivered in last 24h
    yesterday = (datetime.now() - timedelta(days=1)).isoformat()
    cursor.execute(
        "SELECT COUNT(*) FROM delivered WHERE delivered_at > ?",
        (yesterday,)
    )
    last_24h = cursor.fetchone()[0]
    
    # Top 5 recipients by count
    cursor.execute("""
        SELECT recipient, COUNT(*) as count
        FROM delivered
        GROUP BY recipient
        ORDER BY count DESC
        LIMIT 5
    """)
    top_recipients = cursor.fetchall()
    
    click.echo(f"\n📊 Pebbles Status\n")
    click.echo(f"Total delivered: {total}")
    click.echo(f"Last 24h: {last_24h}")
    click.echo(f"\nTop 5 recipients:")
    for recipient, count in top_recipients:
        click.echo(f"  {recipient}: {count} pebbles")
    click.echo()


if __name__ == '__main__':
    cli()