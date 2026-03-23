"""
Pebble CLI — run the engine manually or on a loop.
"""

import asyncio
import time
import click
from pebbles.config import Settings
from pebbles.engine import PebbleEngine


@click.group()
def cli():
    """Pebble — autonomous content discovery for Song."""
    pass


@cli.command()
@click.option("--loop", is_flag=True, help="Run continuously on an interval")
@click.option("--interval", default=300, help="Seconds between runs (default: 300)")
def run(loop: bool, interval: int):
    """Run the pebble engine once or continuously."""
    settings = Settings()
    engine = PebbleEngine(settings)
    
    if loop:
        click.echo(f"🔄 Starting pebble loop (every {interval}s). Press Ctrl+C to stop.")
        try:
            while True:
                asyncio.run(engine.run())
                click.echo(f"💤 Sleeping for {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            click.echo("\n👋 Pebble loop stopped")
    else:
        asyncio.run(engine.run())


if __name__ == "__main__":
    cli()