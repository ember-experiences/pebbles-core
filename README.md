# 🪨 Pebbles

**A smart content discovery engine that brings you interesting things from across the web — like a penguin bringing pebbles to its mate.**

Pebbles monitors multiple sources (Hacker News, Reddit, RSS feeds, YouTube, Letterboxd), matches content against your interests using keyword or semantic matching, and delivers personalized recommendations via Telegram or email. Set daily limits, priority interests, and negative keywords to stay informed without getting overwhelmed.

---

## Quick Start

### Installation

```bash
pip install pebbles-core
```

### Configuration

Create `~/.config/pebbles/config.yaml`:

```yaml
recipients:
  - name: "Jake"
    telegram_id: 123456789
    max_daily_pebbles: 3
    interests:
      - tags: ["surfing", "ocean"]
        keywords: ["surf", "wave", "ocean", "swell"]
        priority: 2
      - tags: ["climbing"]
        keywords: ["climbing", "bouldering", "crag"]
        negative_keywords: ["indoor"]
        priority: 1

sources:
  hackernews:
    enabled: true
  reddit:
    enabled: true
    subreddits: ["surfing", "climbing"]

delivery:
  telegram:
    bot_token: "your-bot-token-here"

matching:
  use_semantic_matching: false
  semantic_threshold: 0.35
```

### Run

```bash
# One-time fetch
pebbles run

# Continuous loop (checks every 30 minutes)
pebbles run --loop
```

---

## Configuration Reference

### Recipients

Each recipient defines who receives pebbles and what they care about:

```yaml
recipients:
  - name: "Jake"                    # Display name
    telegram_id: 123456789          # Optional: Telegram user ID
    email: "jake@example.com"       # Optional: Email address
    max_daily_pebbles: 3            # Daily limit (default: 5)
    interests:
      - tags: ["surfing"]           # Category tags
        keywords: ["surf", "wave"]  # Match keywords
        negative_keywords: ["pool"] # Exclude keywords
        priority: 2                 # 1=normal, 2=high, 3=must-have
```

At least one of `telegram_id` or `email` must be provided per recipient.

### Sources

#### Hacker News
```yaml
sources:
  hackernews:
    enabled: true
```

#### Reddit
```yaml
sources:
  reddit:
    enabled: true
    subreddits:
      - "surfing"
      - "climbing"
      - "technology"
```

#### RSS Feeds
```yaml
sources:
  rss:
    enabled: true
    feeds:
      - "https://example.com/feed.xml"
      - "https://blog.example.com/rss"
```

#### YouTube
```yaml
sources:
  youtube:
    enabled: true
    api_key: "your-youtube-api-key"
    queries:
      - "surf documentary"
      - "climbing training"
```

#### Letterboxd
```yaml
sources:
  letterboxd:
    enabled: true
    usernames:
      - "username1"
      - "username2"
```

### Delivery

#### Telegram
```yaml
delivery:
  telegram:
    bot_token: "your-telegram-bot-token"
```

#### Email
```yaml
delivery:
  email:
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    smtp_user: "you@gmail.com"
    smtp_password: "your-app-password"
    smtp_from: "Pebbles <you@gmail.com>"  # Optional
```

### Matching

```yaml
matching:
  use_semantic_matching: false    # Enable AI-powered matching
  semantic_threshold: 0.35        # Similarity threshold (0.0-1.0)
```

**Semantic matching** uses sentence-transformers (all-MiniLM-L6-v2) for contextual understanding. Falls back to keyword matching if unavailable.

---

## Deployment

### Docker

```bash
docker run -d \
  --name pebbles \
  -v $(pwd)/config:/root/.config/pebbles \
  -v $(pwd)/data:/root/.local/share/pebbles \
  --env-file .env \
  pebbles-core:latest
```

### Docker Compose

```yaml
services:
  pebbles:
    image: pebbles-core:latest
    volumes:
      - ./config:/root/.config/pebbles
      - ./data:/root/.local/share/pebbles
    env_file: .env
    restart: unless-stopped
```

Create `.env`:
```
TELEGRAM_BOT_TOKEN=your-token
SMTP_PASSWORD=your-password
```

---

## Roadmap

Pebbles was built in phases:

- **Phase 1:** Core engine + HackerNews source
- **Phase 2:** Production hardening (logging, retries, error handling)
- **Phase 3:** Multi-source expansion (Reddit, RSS, YouTube, Letterboxd)
- **Phase 4:** Smart matching (semantic understanding, priority scoring, frequency caps)
- **Phase 5:** Polish + ship (email delivery, Docker deployment, docs)

Future ideas: Mastodon source, Discord delivery, web dashboard, collaborative filtering.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add sources, delivery adapters, or improve matching.

---

## License

MIT