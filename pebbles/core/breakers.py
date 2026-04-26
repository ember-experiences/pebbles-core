"""CircuitBreaker — threshold-based pausing.

Sits ABOVE the pipeline as a gate. The check function reads system signals
(metric history, Lucky/Song panic flags, etc.) and decides whether the next
sweep happens.

Per Song's D8 refinement: a custom CircuitBreakerOpenError exception lets
callers distinguish "breaker doing its job" from "actual failure."
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while a breaker is tripped/open.

    Distinct from generic exceptions so schedulers can handle gracefully:
        try:
            run_pipeline()
        except CircuitBreakerOpenError as e:
            metrics.emit(p.id, "sweep_skipped", metadata={"breakers": e.tripped_names})
            return  # don't retry, breaker reset is manual
        except Exception as e:
            # actual failure — alert, retry, etc.
            ...
    """

    def __init__(self, tripped_names: list[str], message: Optional[str] = None):
        self.tripped_names = tripped_names
        if message is None:
            message = f"Circuit breaker(s) open: {', '.join(tripped_names)}"
        super().__init__(message)


@dataclass
class CircuitBreaker:
    """A named circuit breaker.

    `check` returns True if the breaker should TRIP given current state.
    Caller (e.g. Presence's scheduler) periodically calls `evaluate()` or
    relies on BreakerSet.assert_clear() to gate execution.
    """

    name: str
    check: Callable[[], bool]
    on_trip: Optional[Callable[[str], None]] = None
    on_resume: Optional[Callable[[str], None]] = None
    tripped: bool = False
    tripped_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def evaluate(self) -> bool:
        """Run check. Trip if newly true. Returns current tripped state.

        Per D8 design: exceptions in `check` propagate. Caller is responsible
        for catching observability gaps.
        """
        if self.check() and not self.tripped:
            self.tripped = True
            self.tripped_at = datetime.now(timezone.utc).isoformat()
            if self.on_trip:
                self.on_trip(self.name)
        return self.tripped

    def resume(self) -> None:
        """Reset the breaker. Idempotent."""
        if self.tripped:
            self.tripped = False
            self.tripped_at = None
            if self.on_resume:
                self.on_resume(self.name)


class BreakerSet:
    """Collection of CircuitBreakers. Anything tripped → caller pauses."""

    def __init__(self, breakers: list[CircuitBreaker]):
        self.breakers: dict[str, CircuitBreaker] = {b.name: b for b in breakers}

    def evaluate_all(self) -> list[str]:
        """Run every breaker's check. Returns names of currently-tripped breakers."""
        return [b.name for b in self.breakers.values() if b.evaluate()]

    def any_tripped(self) -> bool:
        return any(b.tripped for b in self.breakers.values())

    def tripped_names(self) -> list[str]:
        return [n for n, b in self.breakers.items() if b.tripped]

    def assert_clear(self) -> None:
        """Raise CircuitBreakerOpenError if any breaker is currently tripped.

        Convenience for pipeline gates:
            self.breakers.assert_clear()  # raises if blocked
            run_drafter()
        """
        # Re-evaluate first so check functions run
        self.evaluate_all()
        names = self.tripped_names()
        if names:
            raise CircuitBreakerOpenError(tripped_names=names)

    def resume(self, name: str) -> None:
        """Reset a specific breaker by name. KeyError if name unknown."""
        if name not in self.breakers:
            raise KeyError(f"Unknown breaker: {name}")
        self.breakers[name].resume()

    def resume_all(self) -> None:
        """Reset all breakers."""
        for b in self.breakers.values():
            b.resume()
