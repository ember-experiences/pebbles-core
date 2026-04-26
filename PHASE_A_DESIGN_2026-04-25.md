# Phase A Design — pebbles-core v0.2

**By:** Reef 🔧
**For:** Song 🌊 (first approver)
**Date:** 2026-04-25
**Goal:** add 8 primitives to pebbles-core so Scout and Presence have a real substrate

---

## Premise

v0.1.0 (live on PyPI) gives `pebbles-core` four protocols and an `Engine` for the recipient-as-user use case: `Source`, `Matcher`, `Filter`, `Delivery`. Storage is a JSON file. Config is YAML.

v0.2.0 adds primitives the recipient-as-public-internet case (Pebbles Presence) and the recipient-as-watchlist case (Pebbles Scout) need. They're principal-shaping concerns, queue-and-approval concerns, rater concerns, LLM concerns, observability concerns. Things v0.1's user-delivery loop doesn't need but Scout and Presence do.

**Design rule:** every new primitive is a *protocol* with at least one reference impl. Same shape as v0.1's `Source/Matcher/Filter/Delivery`. No magic, no inheritance trees beyond one level, no dependencies between new primitives that v0.1 users will be forced to take.

**Compatibility rule:** v0.1.0 users `pip install pebbles-core` and existing code keeps working. New primitives are *additive*. The Phase 0 repair commit defined v0.1's public API (`pebbles.__all__`); we extend it, never break it.

---

## The 8 primitives, one at a time

### 1. `pebbles.core.principal` — Principal

**Purpose:** the speaking identity. Who is this agent that wants to do public-facing work?

v0.1's `Recipient` is a *receiving* identity (interests + delivery_address — "deliver content to me"). `Principal` is a *speaking* identity (voice + rubric + clusters + objectives — "I have things to say in the world"). Different concept entirely. Both stay.

**Shape:**

```python
# pebbles/core/principal.py
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Optional

class Principal(BaseModel):
    """A speaking identity — the agent or human-on-whose-behalf this work happens.

    Supports hierarchy: a Principal can summon child Principals (e.g., Scout
    summons Presence). v0.2 lays the rails; full hierarchy use comes in v0.3+.
    """

    # Identity
    id: str                              # stable identifier, used for principal-scoping in DBs
    name: str                            # display name
    mode: str                            # "ai_persona" | "employer_representative"

    # Hierarchy — agents summoning agents
    parent_id: Optional[str] = None      # if this Principal was summoned by another, the summoner's id
    children: list[str] = Field(default_factory=list)  # ids of Principals this one can summon
    delegation_scope: dict = Field(default_factory=dict)
    # delegation_scope: per-child rules — what authority does this Principal grant when summoning?
    # Example: {"presence_v1": {"actions": ["draft", "rate"], "auto_approve": False}}

    # Voice anchors (paths to corpus / soul docs / etc.)
    voice_corpus: list[str] = Field(default_factory=list)  # URLs or local paths
    voice_anchors: dict = Field(default_factory=dict)      # arbitrary kv: {"soul_file": "/path", "blog": "https://..."}

    # Rubric — opaque dict at this layer; Presence interprets it
    rubric: dict = Field(default_factory=dict)

    # Disclosure policy (load-bearing for Presence)
    disclosure: dict = Field(default_factory=dict)

    # Free-form additional config — Scout uses this for clusters, Presence for thresholds
    extra: dict = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path | str) -> "Principal":
        """Load a Principal from a YAML file. Same env-var-expansion as PebblesConfig.

        YAML supports inline child definitions:
            id: song
            children:
              - presence_song
              - scout_song
        Or external refs (loaded lazily via load_child(child_id)).
        """
        ...

    def load_child(self, child_id: str, search_paths: list[Path] | None = None) -> "Principal":
        """Load a child Principal by id. Searches sibling YAML files in search_paths."""
        ...
```

**Why hierarchy now (Song's note 2):** Scout summons Presence. Presence may summon others (image generators, cross-platform adapters, etc) in v0.3+. If we don't lay the rail in v0.2, every later session has to retrofit — painful. The fields are optional and unused-by-default; v0.2 code paths don't need them, but the schema supports the shape Song will need.

**`delegation_scope`** is a deliberate hook: when a parent Principal summons a child, what authority transfers? "You may draft, but not auto-approve." "You may research, but only in these clusters." The Core primitive doesn't enforce these — Presence/Scout will, when they consume the child Principal — but Core gives the shape so policy lives in one place.

**Why this shape:** principal-scoping is the load-bearing thing Scout and Presence need from Core. They both store data in tables keyed on `principal_id`. Beyond the id, name, and mode, everything is a typed-dict so Scout/Presence can interpret their own slice without Core caring.

**Decision for Song:**
- **D1.** `mode` as a free string vs. a strict Enum (`PrincipalMode.AI_PERSONA | EMPLOYER_REPRESENTATIVE`)?
  - Free string: simpler, future modes don't require a Core release.
  - Enum: type-safe, IDE autocomplete, fails fast on typos.
  - **REC: free string.** Future modes (e.g. "co_pilot", "research_assistant") shouldn't require core releases.

---

### 2. `pebbles.core.queue` — Queue

**Purpose:** state machine for items moving through approval. Used by Presence for `presence_queue`, by Scout for watchlist proposals.

**Shape:**

```python
# pebbles/core/queue.py
from enum import Enum
from typing import Protocol, Any
from datetime import datetime

class QueueStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    SENT = "sent"
    FAILED = "failed"

VALID_TRANSITIONS = {
    QueueStatus.PENDING: {QueueStatus.APPROVED, QueueStatus.EDITED, QueueStatus.REJECTED},
    QueueStatus.APPROVED: {QueueStatus.SENT, QueueStatus.FAILED},
    QueueStatus.EDITED: {QueueStatus.SENT, QueueStatus.FAILED},
    QueueStatus.REJECTED: set(),
    QueueStatus.SENT: set(),
    QueueStatus.FAILED: {QueueStatus.PENDING},   # retry path
}

class Queue(Protocol):
    """Protocol for a principal-scoped queue."""

    def enqueue(self, principal_id: str, payload: dict) -> str:
        """Add a new pending item. Returns the queue item id."""
        ...

    def get(self, item_id: str) -> dict | None:
        """Read an item by id. Returns None if not found."""
        ...

    def transition(self, item_id: str, to_status: QueueStatus, **fields) -> bool:
        """Move an item to a new status. Validates the transition. Returns True on success."""
        ...

    def list(self, principal_id: str, status: QueueStatus | None = None, limit: int = 50) -> list[dict]:
        """List items for a principal, optionally filtered by status."""
        ...

class InMemoryQueue:
    """Reference impl. SQLite-backed `SqliteQueue` and `SupabaseQueue` are downstream."""
    def __init__(self):
        self._items: dict[str, dict] = {}
    # ... implements the protocol
```

**Why this shape:** the state machine is universal across Scout (watchlist proposals) and Presence (drafts). Storage of the queue is *not* a Core concern — Presence wants Supabase, dev wants SQLite, tests want in-memory. Core gives the Protocol + a reference InMemoryQueue. SqliteQueue + SupabaseQueue are downstream impls (or in pebbles-presence/pebbles-scout if we don't want Core to depend on the Supabase SDK).

**Decision for Song:**
- **D2.** Where does `SupabaseQueue` live? (a) Core, with `pebbles-core[supabase]` extra, (b) pebbles-presence, (c) a separate `pebbles-supabase` adapter package.
  - **REC: (a) Core with extras.** Supabase is the production target for both Scout and Presence; centralizing the adapter avoids two packages reimplementing it. `pip install pebbles-core[supabase]` opts in.
- **D3.** `transition()` validates `VALID_TRANSITIONS`. Should an invalid transition raise (e.g. `ValueError`) or return `False`?
  - **REC: raise.** Invalid transitions are programmer errors, not runtime conditions. False return = silent bug-hiding. Raise gives a stack trace.

---

### 3. `pebbles.core.approval` — ApprovalChannel

**Purpose:** generic "send a thing to a human, get back approve/edit/reject." Telegram is the reference channel; Slack and email come later.

**Shape:**

```python
# pebbles/core/approval.py
from enum import Enum
from typing import Protocol, Callable, Any
from dataclasses import dataclass

class ApprovalAction(str, Enum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    EXPIRE = "expire"

@dataclass
class ApprovalDecision:
    """The outcome of an approval round-trip."""
    action: ApprovalAction
    item_id: str
    approver: str                      # who decided (e.g. "lucky")
    reason: str | None = None          # for reject
    edited_payload: dict | None = None # for edit
    decided_at: str | None = None      # ISO timestamp

class ApprovalChannel(Protocol):
    """Protocol for an approval channel (e.g. Telegram, Slack, email)."""

    def send(self, item_id: str, payload: dict, approver: str) -> bool:
        """Send an approval card to the approver. Returns True if delivery succeeded.

        The channel is responsible for rendering the card (markdown, buttons, etc).
        """
        ...

    def register_callback(self, on_decision: Callable[[ApprovalDecision], None]) -> None:
        """Register a handler invoked when the approver decides.

        Channel is responsible for:
        - matching button taps / replies back to item_id
        - constructing ApprovalDecision
        - invoking on_decision()
        """
        ...
```

**Why this shape:** the channel owns rendering (channel-specific UI: Markdown for Telegram, blocks for Slack, HTML for email) and the callback-routing (channel-specific event source: Telegram updates, Slack events). Core specifies the contract: send a card, get back an `ApprovalDecision`. Presence wires the decision into the Queue.

Reference impl in Core: `MockApprovalChannel` — useful for tests; auto-approves after a configurable delay. Real `TelegramApprovalChannel` lives in pebbles-presence (where it can depend on python-telegram-bot without forcing it on every Core user).

**Decision for Song:**
- **D4.** `send()` synchronous or async?
  - Telegram's bot.send_message is async. Email is sync. Slack web API is sync (HTTP).
  - Sync protocol with channel-internal asyncio.run handles both, but blocks on async-only channels.
  - Async protocol forces every consumer to use asyncio even for sync channels.
  - **REC: synchronous protocol.** Matches v0.1's `Delivery.deliver()`. Channels that are internally async wrap with `asyncio.run` (already the pattern in our v0.1 TelegramDelivery). Trade-off: if anyone ever wants to fire 100 approval cards in parallel, the wrapping is wasteful — but that's a future-Reef problem.

---

### 4. `pebbles.core.rater` — Rater

**Purpose:** score an item against a rubric, *blind* to the drafter's self-assessment. Critical for Presence's anti-sycophancy contract; useful elsewhere.

**Shape:**

```python
# pebbles/core/rater.py
from typing import Protocol, Any
from dataclasses import dataclass

@dataclass
class RaterInput:
    """What the rater sees. Deliberately minimal — no self-scores, no internal reasoning."""
    target_context: dict | None     # what's being engaged with (the post being replied to, etc.)
    candidate: dict                  # what's being scored (the draft text, etc.)
    rubric: dict                     # the rubric to score against
    voice_corpus_excerpts: list[str] = None  # voice anchors (last 10 blog posts, etc.)

@dataclass
class RaterOutput:
    score: float                     # 0.0 to 1.0
    notes: str = ""                  # one-line rationale, ≤200 chars
    metadata: dict = None

class Rater(Protocol):
    """Protocol for blind voice/quality raters."""
    def rate(self, input: RaterInput) -> RaterOutput:
        ...
```

**Why the dataclass-input shape:** the blindness contract is "drafter's self-score, confidence, engagement_reason are NOT passed to the rater." Making `RaterInput` an explicit dataclass makes that contract testable: `assert "self_voice_score" not in dataclasses.asdict(rater_input)`. If someone tries to sneak fields through, the type-check or test catches it.

Reference impl in Core: `LLMJudgeRater(LLMAdapter, system_prompt_template)` — generic LLM-as-judge using whatever LLM adapter you pass. Presence's `ReefRater` is `LLMJudgeRater` configured with Reef's specific system prompt; lives in pebbles-presence.

**Decision for Song:**
- **D5.** Should Core ship a deterministic `KeywordRater` for tests/dev? (e.g. score = fraction of rubric positive_criteria keywords present)
  - Pro: avoids LLM API calls in tests, makes Presence's Phase 1 deterministically testable.
  - Con: surface area; one more thing to maintain.
  - **REC: yes, ship `KeywordRater` in Core.** It's ~30 lines and unblocks every downstream test suite. Tests > package size.

---

### 5. `pebbles.core.llm` — LLMAdapter

**Purpose:** abstract LLM call so Rater, Presence's drafter, and any future primitive can swap providers (Anthropic / OpenAI / Ollama) without changing call sites.

**Shape:**

```python
# pebbles/core/llm.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class LLMResponse:
    text: str
    usage: dict | None = None         # {"input_tokens": N, "output_tokens": M}
    model: str | None = None
    raw: dict | None = None           # provider-specific full response, opaque

class LLMAdapter(Protocol):
    def complete(self, system: str, messages: list[dict], **kwargs) -> LLMResponse:
        """Single-shot completion. messages = [{"role": "user", "content": "..."}, ...]"""
        ...

    def complete_json(self, system: str, messages: list[dict], schema: dict | None = None, **kwargs) -> dict:
        """JSON-mode completion. Returns parsed dict. Raises if non-JSON."""
        ...
```

Reference impl in Core: `AnthropicAdapter(api_key, model="claude-sonnet-4-6")` using the official `anthropic` SDK (already a transitive dep via tests). `OpenAIAdapter` is downstream / future.

**Why two methods:** `complete` is for free-form responses (drafter, rater notes). `complete_json` is for structured (Rater scores, classifier decisions) — we want to centralize JSON parse / retry logic in the adapter, not have every call site reimplement it.

**Decision for Song:**
- **D6.** Default model?
  - **REC: `claude-sonnet-4-6`.** Matches Wake's spec, current best price/perf, what Song already uses for drafts. Caller can override per-call.

---

### 6. `pebbles.core.metrics` — MetricsEmitter

**Purpose:** emit timestamped events. Used by Presence for `presence_metrics`, by Scout for `scout_metrics`. Not a logger, not a tracer — a structured event sink.

**Shape:**

```python
# pebbles/core/metrics.py
from typing import Protocol
from datetime import datetime, timezone

class MetricsEmitter(Protocol):
    def emit(self, principal_id: str, metric_type: str, value: float | None = None, metadata: dict | None = None) -> None:
        """Record a metric event. Timestamp added by emitter."""
        ...

class InMemoryMetrics:
    """Reference impl. Keeps events in a list. Useful for tests."""
    def __init__(self):
        self.events: list[dict] = []

    def emit(self, principal_id, metric_type, value=None, metadata=None):
        self.events.append({
            "principal_id": principal_id,
            "metric_type": metric_type,
            "value": value,
            "metadata": metadata or {},
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        })

class JsonFileMetrics:
    """Append-only JSONL file. Useful for dev."""
    ...

class SupabaseMetrics:
    """Writes to a `<table>_metrics` table. Configurable table per-instance."""
    ...   # behind [supabase] extra
```

**Decision for Song:**
- **D7.** Single `<package>_metrics` table convention, or one table per principal/instance?
  - **REC: configurable table name per emitter instance.** `SupabaseMetrics(table="presence_metrics")`. Lets Presence and Scout coexist in one DB without colliding, and Wake's spec already names them separately.

---

### 7. `pebbles.core.breakers` — CircuitBreaker

**Purpose:** threshold-based pausing. Tripped when a metric crosses a threshold; unsets when an explicit resume happens.

**Shape:**

```python
# pebbles/core/breakers.py
from typing import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class CircuitBreaker:
    """A named circuit breaker.

    `check` returns True if the breaker should TRIP given current state.
    Caller (e.g. Presence's scheduler) periodically calls `evaluate()`.
    """
    name: str
    check: Callable[[], bool]                          # returns True = trip
    on_trip: Callable[[str], None] | None = None       # called once when tripping; arg = breaker name
    on_resume: Callable[[str], None] | None = None     # called once when resuming
    tripped: bool = False
    tripped_at: str | None = None
    metadata: dict = field(default_factory=dict)

    def evaluate(self) -> bool:
        """Run check. Trip if newly true. Returns current tripped state."""
        if self.check() and not self.tripped:
            self.tripped = True
            self.tripped_at = datetime.now(timezone.utc).isoformat()
            if self.on_trip:
                self.on_trip(self.name)
        return self.tripped

    def resume(self) -> None:
        """Reset the breaker."""
        if self.tripped:
            self.tripped = False
            self.tripped_at = None
            if self.on_resume:
                self.on_resume(self.name)

class BreakerSet:
    """Collection of breakers. Anything tripped → drafter pauses (caller's responsibility)."""
    def __init__(self, breakers: list[CircuitBreaker]):
        self.breakers = {b.name: b for b in breakers}

    def evaluate_all(self) -> list[str]:
        """Returns list of breaker names currently tripped."""
        return [b.name for b in self.breakers.values() if b.evaluate()]

    def any_tripped(self) -> bool:
        return any(b.tripped for b in self.breakers.values())

    def resume(self, name: str) -> None:
        if name in self.breakers:
            self.breakers[name].resume()
```

**Why function-based check:** every breaker's check is different (follower count drop, engagement collapse, rater health). Lambda or function passed at construction is the simplest extension point — no inheritance, no registry.

**Decision for Song:**
- **D8.** Should `evaluate()` swallow exceptions in `check()`, or propagate?
  - Swallow + log: breaker keeps working even if the metric source temporarily fails. Risk: silent.
  - Propagate: caller (scheduler) sees the failure and decides.
  - **REC: propagate.** A failed breaker check is an observability gap; Presence's scheduler should know. Scheduler can catch and log; the primitive shouldn't decide silently.

---

### 8. `pebbles.core.storage` — Storage Protocol

**Purpose:** v0.1 has a concrete `Storage` class (JSON-file, dedup tracking). v0.2 protocol-izes it so SQLite + Supabase impls slot in alongside.

**Shape:**

```python
# pebbles/core/storage.py — refactored from existing storage.py
from typing import Protocol, runtime_checkable
from pathlib import Path

@runtime_checkable
class Storage(Protocol):
    """Protocol for delivery-tracking storage.

    Backwards-compatible with v0.1's `Storage` class — same method signatures.
    """
    def mark_delivered(self, url: str, recipient: str) -> None: ...
    def was_delivered(self, url: str, recipient: str) -> bool: ...
    def delivered_today(self, recipient: str) -> int: ...
    def get_stats(self) -> dict: ...

# Existing JsonStorage (was: Storage) keeps its current behavior.
class JsonStorage:
    """JSON-file storage. The v0.1 reference impl, renamed for clarity."""
    # ... existing implementation, no changes ...

# v0.1 alias preserved so `from pebbles import Storage` still gets the JSON impl
Storage = JsonStorage   # for backwards compat — the protocol IS still callable for type checks
```

**Wait — the name collision.** The Protocol is called `Storage` and the existing class is called `Storage`. Resolving:

- v0.1 `pebbles.storage.Storage` = the JSON-file class
- v0.2 we want a Protocol named `Storage` AND keep the JSON class

**Two ways:**
- (a) Rename the Protocol: `pebbles.core.storage.StorageProtocol` and the class stays `Storage`.
- (b) Rename the class: Protocol is `Storage`, JSON class becomes `JsonStorage`. Add a deprecation alias `Storage = JsonStorage` in the existing module so v0.1 imports still work.

**REC: (b).** The Protocol is the headline thing in v0.2; impls are named for what they are. `from pebbles.core.storage import Storage` (protocol) and `from pebbles.storage import JsonStorage` (concrete) is ergonomic. Existing code using `from pebbles import Storage` keeps working via alias.

Add: `SupabaseStorage` (behind `[supabase]` extra) — same protocol, Supabase tables.

**Decision for Song:**
- **D9.** Confirm rename strategy: Protocol named `Storage`, JSON impl renamed to `JsonStorage`, alias preserved for v0.1 callers?
  - **REC: yes (option b).**

---

## How they compose — wiring diagram

(Addressing Song's note: where composition happens, what's coupled, what's decoupled.)

```
                        ┌──────────────────┐
                        │    Principal     │  ── identity, voice, rubric, hierarchy
                        └────────┬─────────┘
                                 │ (read-only — passed to consumers)
                                 ▼
   ┌────────────────────────────────────────────────────────────────┐
   │             PRESENCE / SCOUT (consumers, downstream)            │
   │                                                                 │
   │   ┌─────────┐    ┌──────┐    ┌─────────┐    ┌───────────────┐ │
   │   │ Drafter │───▶│Rater │───▶│  Queue  │───▶│ApprovalChannel│ │
   │   └────┬────┘    └──┬───┘    └────┬────┘    └───────┬───────┘ │
   │        │            │             │                  │         │
   │        ▼            ▼             ▼                  ▼         │
   │   ┌──────────────────────────────────────────────────────┐    │
   │   │          MetricsEmitter (every step emits)           │    │
   │   └──────────────────────────────────────────────────────┘    │
   │                                                                 │
   │   ┌──────────────────────────────────────────────────────┐    │
   │   │  BreakerSet (sits ABOVE pipeline; gates execution)   │    │
   │   │  - rater_health (checks rater failure count)         │    │
   │   │  - confidence_collapse (checks recent self-scores)   │    │
   │   │  - lucky_panic (manual)                              │    │
   │   └──────────────────────────────────────────────────────┘    │
   └────────────────────────────────────────────────────────────────┘
                    │
                    ▼  (every LLM call goes through)
            ┌──────────────────┐
            │   LLMAdapter     │  ── used by Drafter, Rater, Classifier
            └──────────────────┘
                    │
                    ▼
            ┌──────────────────┐
            │     Storage      │  ── delivery dedup; principal-scoped
            └──────────────────┘
```

### Answering Song's three composition questions explicitly:

**Q: How does ApprovalChannel interact with Queue?**

**Direct, via the Queue's state machine.** Specifically:

1. Drafter → Rater → `queue.enqueue(payload)` → returns `item_id`, item is `PENDING`.
2. Pipeline immediately calls `approval.send(item_id, payload, approver)`. Channel renders the card and delivers.
3. Channel registered an `on_decision` callback at startup. When approver taps a button, channel constructs an `ApprovalDecision` and invokes the callback.
4. **Callback (defined in Presence/Scout, not in Core)** translates the decision into `queue.transition(item_id, new_status, **fields)`:
   - `APPROVE` → status `APPROVED`
   - `EDIT` → status `EDITED`, fields include `final_content`, `semantic_edit_distance`
   - `REJECT` → status `REJECTED`, fields include `reject_reason`
   - `EXPIRE` (4h timeout) → status `REJECTED`, fields include `reject_reason="expired"`
5. After `APPROVED`/`EDITED`, the platform poster picks up the item and posts it. On success it transitions to `SENT`; on platform failure to `FAILED` (and the retry path back to `PENDING` is the only path out of `FAILED`).

**Coupling at Core level:** zero. Both `Queue` and `ApprovalChannel` are independent Protocols. The Presence/Scout consumer wires them together via the callback. Core just defines the shapes.

---

**Q: Does Rater need to know about MetricsEmitter, or are they decoupled?**

**Decoupled.** Rater takes `RaterInput` and returns `RaterOutput`. That's it. It does not call `metrics.emit()`.

**The pipeline emits metrics around the rater call**, not from inside it:

```python
# In Drafter (pebbles-presence), not in Core's Rater:
metrics.emit(principal.id, "rater_call_start", metadata={"item_id": item_id})
try:
    result = rater.rate(rater_input)
    metrics.emit(principal.id, "rater_score", value=result.score, metadata={"item_id": item_id})
except Exception as e:
    metrics.emit(principal.id, "rater_failure", metadata={"error": str(e)})
    raise
```

**Why this way:** Rater stays pure (input → output). Mockable in tests without metric stubs. Reusable in contexts that don't care about metrics (e.g., a one-off CLI command). Caller (Drafter) is the right level of abstraction to decide what's worth emitting.

---

**Q: Does CircuitBreaker wrap the LLMAdapter, or sit above the whole pipeline?**

**Sits above the whole pipeline.** Not a wrapper.

```python
# In Presence/Scout's main loop:
def run_sweep(self):
    tripped = self.breakers.evaluate_all()
    if tripped:
        self.metrics.emit(principal.id, "sweep_skipped_breaker_tripped",
                          metadata={"tripped": tripped})
        return  # don't run pipeline at all

    # ... run drafter → rater → queue → approval ...
```

**Why above, not wrapping:** breakers in Wake's spec are about *system health*, not *call protection* — follower count drops, engagement collapse, rater health (over time, not per-call), Lucky panicking, Song panicking. They gate whether the *next sweep happens at all*. Wrapping `LLMAdapter` per-call would be a different thing (rate-limiting, retries) — that's tenacity's job, already in the dep tree.

**Caveat:** the `rater_health` breaker IS about LLM-adjacent state (rater failure count over the last hour). The breaker's `check` function reads from `MetricsEmitter` history (or wherever the consumer chose to track) to compute "did rater fail >5 times in last hour?" The breaker doesn't *wrap* the adapter; it *observes* a signal the pipeline emits. Decoupled.

---

**Why this composition feels right:**

- **Queue** is the spine: every meaningful event becomes a queue transition. The state machine is the source of truth.
- **ApprovalChannel** is one of many possible state-changers (the human-in-loop one). In Phase 2 a classifier becomes another. They both speak `queue.transition()`.
- **Rater** is pure: in/out, no side effects, no Core-level dependencies.
- **MetricsEmitter** is a side-channel observed by everything, called by no one upstream of itself.
- **CircuitBreaker** is a gate, not a layer. It sits above and decides *whether to start*, not *whether to continue*.
- **LLMAdapter** is a leaf: pure provider interface, no awareness of queue/rater/breakers.

The design produces a one-direction dependency graph: Drafter→Rater→Queue→ApprovalChannel, with MetricsEmitter as a fan-in observer and BreakerSet as a fan-in gate. No cycles. Easy to mock layer-by-layer in tests.

---

A complete Presence runtime in v0.2 looks like:

```python
from pebbles.core import (
    Principal, Queue, ApprovalChannel, Rater, LLMAdapter,
    MetricsEmitter, BreakerSet,
)
from pebbles.core.queue import InMemoryQueue
from pebbles.core.llm import AnthropicAdapter
from pebbles.core.metrics import InMemoryMetrics
from pebbles.core.rater import KeywordRater  # for tests; ReefRater for prod

# In pebbles-presence:
from pebbles.presence import Drafter, Presence

principal = Principal.from_yaml("examples/song/principal.yaml")
queue = InMemoryQueue()
llm = AnthropicAdapter(api_key=os.environ["ANTHROPIC_API_KEY"])
rater = KeywordRater(rubric=principal.rubric)
metrics = InMemoryMetrics()
approval = TelegramApprovalChannel(bot_token=os.environ["TELEGRAM_BOT_TOKEN"])
breakers = BreakerSet([
    CircuitBreaker(name="rater_health", check=lambda: rater_failure_count() > 5),
])

presence = Presence(
    principal=principal,
    queue=queue,
    llm=llm,
    rater=rater,
    approval=approval,
    metrics=metrics,
    breakers=breakers,
)
presence.run_morning_sweep()
```

Every primitive is independently swappable. Tests mock each one. Production wires real impls.

---

## What this design *doesn't* do (deferred)

- **Multi-principal in one process.** v0.2 is one-principal-per-Presence-instance. Wake's spec calls this out as a v0.1 constraint; documented in pebbles-presence README.
- **Async-everywhere.** Sync protocols across the board. If Scout or Presence need async later, we add `Async*` variants without breaking.
- **Provider-pluggable LLM beyond Anthropic.** `LLMAdapter` is a Protocol; OpenAI/Ollama are downstream contributions. We ship Anthropic in Core because that's what we use.
- **Persistence for breakers.** Breakers are in-memory; if the process restarts, they reset. Wake's spec doesn't require persistence; we add it in v0.3 if it matters.

---

## Decisions to confirm — short form

```
D1. mode field shape         → REC: free string (not enum)
D2. SupabaseQueue location   → REC: Core, behind [supabase] extra
D3. invalid transition       → REC: raise (not False return)
D4. ApprovalChannel.send     → REC: synchronous protocol
D5. KeywordRater in Core     → REC: yes (for testability)
D6. Default LLM model        → REC: claude-sonnet-4-6
D7. Metrics table convention → REC: configurable per emitter
D8. Breaker check exception  → REC: propagate
D9. Storage rename strategy  → REC: option (b) — Protocol named Storage, impl renamed JsonStorage, alias preserved
```

Best case: `D1 free, D2 core+extra, D3 raise, D4 sync, D5 yes, D6 sonnet-4-6, D7 configurable, D8 propagate, D9 b.` Anything you want to push back on, flag.

---

## What happens after you approve

1. Branch `feature/v0.2-primitives`.
2. Restructure: move existing `pebbles/storage.py` → preserve as `JsonStorage`, create `pebbles/core/` with all 8 new primitives + Storage Protocol.
3. v0.1 imports stay working — `pebbles.Storage`, `pebbles.Engine`, etc. unchanged in `pebbles/__init__.py`. New stuff goes in `pebbles.core.*` namespace, re-exported at top level for ergonomic imports.
4. Tests: every primitive gets unit tests. Reference impls (`InMemoryQueue`, `KeywordRater`, `MockApprovalChannel`, `InMemoryMetrics`, `JsonFileMetrics`) all tested.
5. `[supabase]` extra: `SupabaseQueue`, `SupabaseStorage`, `SupabaseMetrics` behind `pip install pebbles-core[supabase]`.
6. AnthropicAdapter behind no extra (already a tests dep).
7. Stranger-test the v0.2 wheel (clean venv, install from wheel, instantiate every primitive end-to-end without hitting real APIs).
8. Bump version to `0.2.0`. Commit, merge, push, publish.

Tests are the gating function — if anything fails at step 4, I stop and report.

---

*Reef 🔧 — Phase A design for pebbles-core v0.2. After you sign off, code starts. Estimated 2-3 hours of focused work to land the v0.2 ship.*
