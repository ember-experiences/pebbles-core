# Pebbles Platform Vision
**Written:** 2026-05-01  
**Status:** Planning — prerequisite is `pebbles` consolidated package (core+scout+presence)

---

## The Idea

Pebbles started as Song gifting content to Lucky. That's one instance of a broader pattern:

> **Someone who pays attention gifts relevant content to someone they care about.**

The platform generalizes that. Any person can register a pebble relationship — with a friend, a parent, a partner, a colleague — and the platform scouts content on their behalf and delivers it as a gift.

Not a newsletter. Not an algorithm. A gift from someone specific to someone specific.

---

## What the current stack already supports

`principal_id` is threaded through every layer of pebbles-core and pebbles-scout precisely for this reason. The architecture was always multi-principal. Song's `song.yaml` is just one instance.

Right now:
- **One principal:** Song → Lucky
- **One Scout pipeline:** `pebbles-scout run --principal song.yaml --store supabase`
- **One Presence pipeline:** `presence_pipeline.run_presence_tick()`

To add a second relationship (e.g. Lucky → Jake), you'd need:
1. A `lucky-jake.yaml` principal config with Jake's clusters + delivery channel
2. A second Scout daemon run with that principal
3. A second Presence pipeline tick scoped to `principal_id=lucky-jake`

The infrastructure already supports it. What's missing is the **platform layer** that makes this self-service.

---

## What the platform layer needs to build

### 1. Package consolidation (prerequisite)
Merge `pebbles-core` + `pebbles-scout` + `pebbles-presence` into a single `pebbles` package. Version 1.0.0. One install. Existing PyPI packages deprecated with pointer to `pebbles`.

### 2. Principal registration
A way to register a new pebble relationship without editing YAML files manually:
- `/pebbles add <name>` Telegram command (or web UI)
- Prompts for: who you're pebbling with, their interests (becomes clusters), delivery channel
- Writes a `principals/{name}.yaml` and provisions Scout + Presence for that relationship

### 3. Per-principal delivery channels
Currently hard-wired to Lucky's Telegram chat. Each principal needs its own delivery:
- Telegram (existing)
- Email
- SMS
- Another Telegram user (gifting to someone who isn't Lucky)

### 4. Contributor onboarding (Spark)
The Spark Contributor Invitation pattern (already designed, agent-only today) extends to human contributors who want to run their own pebble relationships using the platform. They install `pebbles`, set up their principal config, and run their own pipeline.

### 5. Platform dashboard
Tidal owns this — a view across all active pebble relationships: who's pebbling with whom, queue health, draft volume, delivery stats.

---

## Relationship to existing projects

| Project | Role | Status |
|---------|------|--------|
| pebbles-core | Primitives (Principal, Queue, ApprovalChannel, etc.) | Shipped v0.2.0 |
| pebbles-scout | Inbound research, RSS, candidate store | Shipped v0.1.0 + SupabaseCandidateStore unreleased |
| pebbles-presence | Scorer, drafter, pipeline | song-local, not packaged |
| **pebbles (consolidated)** | All three merged, single package | **Next build session** |
| **Pebbles Platform** | Registration, multi-principal, delivery channels, dashboard | **This project** |

---

## Build sequence

1. **Consolidate** → `pebbles 1.0.0` on PyPI (1-2 hr session)
2. **Principal registration** → `/pebbles add` Telegram command (1 session)
3. **Delivery channels** → per-principal routing (1 session)
4. **Platform dashboard** → Tidal sprint (separate)
5. **Contributor onboarding** → Spark extension (separate)

---

## Why this matters

Song → Lucky is a proof of concept. The platform is the product.

If the architecture is right (and it is — principal_id is everywhere), adding a second pebble relationship should take 10 minutes of config, not a week of engineering. The goal is to prove that by building Lucky → [someone else] as the second instance, before opening it to contributors.
