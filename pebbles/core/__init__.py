"""pebbles.core — primitives for principal-shaped agent capabilities.

Each primitive is a Protocol with at least one reference impl. Downstream
packages (pebbles-presence, pebbles-scout) implement their own variants
or use the Core reference impls directly.

Public API (re-exported at top-level pebbles.* in __init__.py):

- Principal              — speaking identity with hierarchy support
- Queue, QueueStatus, CircuitBreakerOpenError (etc — see individual modules)
- ApprovalChannel, ApprovalAction, ApprovalDecision
- Rater, RaterInput, RaterOutput
- LLMAdapter, LLMResponse
- MetricsEmitter
- CircuitBreaker, BreakerSet, CircuitBreakerOpenError
- Storage (Protocol)

Reference impls live in their own modules and are NOT re-exported here
to keep the namespace clean. Import explicitly:
    from pebbles.core.queue import InMemoryQueue
    from pebbles.core.metrics import InMemoryMetrics
    from pebbles.core.rater import KeywordRater
    from pebbles.core.llm import AnthropicAdapter
"""

from pebbles.core.principal import Principal
from pebbles.core.queue import Queue, QueueStatus, InvalidTransitionError
from pebbles.core.approval import ApprovalChannel, ApprovalAction, ApprovalDecision
from pebbles.core.rater import Rater, RaterInput, RaterOutput
from pebbles.core.llm import LLMAdapter, LLMResponse
from pebbles.core.metrics import MetricsEmitter
from pebbles.core.breakers import CircuitBreaker, BreakerSet, CircuitBreakerOpenError
from pebbles.core.storage import Storage

__all__ = [
    "Principal",
    "Queue",
    "QueueStatus",
    "InvalidTransitionError",
    "ApprovalChannel",
    "ApprovalAction",
    "ApprovalDecision",
    "Rater",
    "RaterInput",
    "RaterOutput",
    "LLMAdapter",
    "LLMResponse",
    "MetricsEmitter",
    "CircuitBreaker",
    "BreakerSet",
    "CircuitBreakerOpenError",
    "Storage",
]
