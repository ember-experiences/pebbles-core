"""Pebbles — autonomous discovery and delivery engine.

v0.1 (recipient-as-user, shipped on PyPI 2026-04-23):
- Pebble, Recipient, Interest, PebblesConfig
- Engine, Source, Matcher, Filter, Delivery
- Storage (alias for JsonStorage), InterestMatcher

v0.2 (recipient-as-public-internet primitives, this version):
- Principal — speaking identity with hierarchy
- Queue, QueueStatus, InvalidTransitionError
- ApprovalChannel, ApprovalAction, ApprovalDecision
- Rater, RaterInput, RaterOutput
- LLMAdapter, LLMResponse
- MetricsEmitter
- CircuitBreaker, BreakerSet, CircuitBreakerOpenError

Reference impls live in pebbles.core.* submodules and are NOT re-exported
at the top level — keeping the namespace clean. Import explicitly:
    from pebbles.core.queue import InMemoryQueue
    from pebbles.core.metrics import InMemoryMetrics, JsonFileMetrics
    from pebbles.core.rater import KeywordRater, LLMJudgeRater
    from pebbles.core.llm import AnthropicAdapter
    from pebbles.core.approval import MockApprovalChannel
    from pebbles.storage import JsonStorage  # the v0.1 concrete class
"""

__version__ = "0.2.0"

# v0.1 surface — preserved
from pebbles.models import Pebble, Recipient, Interest
from pebbles.config import PebblesConfig
from pebbles.engine import Engine, Source, Matcher, Filter, Delivery
from pebbles.storage import Storage  # alias to JsonStorage; works for v0.1 callers
from pebbles.matcher import InterestMatcher

# v0.2 surface — new primitives
from pebbles.core.principal import Principal
from pebbles.core.queue import Queue, QueueStatus, InvalidTransitionError
from pebbles.core.approval import ApprovalChannel, ApprovalAction, ApprovalDecision
from pebbles.core.rater import Rater, RaterInput, RaterOutput
from pebbles.core.llm import LLMAdapter, LLMResponse
from pebbles.core.metrics import MetricsEmitter
from pebbles.core.breakers import CircuitBreaker, BreakerSet, CircuitBreakerOpenError
from pebbles.core.storage import Storage as StorageProtocol  # the Protocol type

__all__ = [
    # v0.1
    "Pebble",
    "Recipient",
    "Interest",
    "PebblesConfig",
    "Engine",
    "Source",
    "Matcher",
    "Filter",
    "Delivery",
    "Storage",  # alias to JsonStorage
    "InterestMatcher",
    # v0.2 primitives
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
    "StorageProtocol",  # the Protocol shape (different from `Storage` alias)
]
