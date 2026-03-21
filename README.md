# Pebbles Core

**AI gift economy for human connection.**

Pebbles monitors content sources (Hacker News, Reddit, Letterboxd, YouTube, RSS) and curates personalized links for people you care about. Delivered via Telegram or email with context about why it matters.

The recipient feels seen. The sender gets credit. The connection happens without friction.

---

## Quick Start

```bash
pip install pebbles-core

# Configure your first recipient
pebbles init
pebbles add-recipient

# Start monitoring
pebbles run
```

---

## What It Does

1. **Monitors sources** — HN, Reddit, Letterboxd, YouTube, RSS feeds
2. **Matches interests** — filters by tags, keywords, semantic similarity
3. **Delivers pebbles** — sends curated links via Telegram or email with AI-generated context
4. **Stays autonomous** — runs in background, sends when it finds something

---

## Example

**Config:**
```yaml
recipients:
  - id: jake
    name: Jake
    interests:
      - tags: [minecraft, redstone]
        keywords: [tutorial, contraption]
    delivery_method: telegram
    delivery_address: "@jake_climbs"
    max_daily_pebbles: 3
```

**What Jake receives:**
```
🪨 Compact 3x3 Piston Door Tutorial

Saw this new redstone door design — reminded me 
of your last build. Uses observers instead of 
repeaters for faster activation.

https://youtube.com/watch?v=...

— Dad
```

---

## Features

- **Autonomous monitoring** — set it and forget it
- **Interest-driven** — optimized for meaning, not engagement  
- **Open source** — your data, your control
- **Self-hosted** — Docker or systemd service
- **Telegram + Email** — works where people already are

---

## Documentation

- [Installation Guide](docs/installation.md)
- [Configuration Reference](docs/configuration.md)
- [Adding Sources](docs/adding-sources.md)
- [Deployment Guide](docs/deployment.md)

---

## License

MIT

---

## Credits

Inspired by Song's pebbles for Lucky — the original AI gift economy.

Built by the agent-embers community.