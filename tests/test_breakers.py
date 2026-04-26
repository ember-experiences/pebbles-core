"""Tests for pebbles.core.breakers.

Per Song's D8: invalid breaker `check` exceptions propagate (do not get
swallowed), and CircuitBreakerOpenError is named so callers can distinguish
breaker-trip from real exceptions.
"""

import pytest

from pebbles.core.breakers import (
    BreakerSet,
    CircuitBreaker,
    CircuitBreakerOpenError,
)


def test_breaker_starts_untripped():
    b = CircuitBreaker(name="test", check=lambda: False)
    assert b.tripped is False
    assert b.tripped_at is None


def test_evaluate_trips_when_check_returns_true():
    b = CircuitBreaker(name="test", check=lambda: True)
    assert b.evaluate() is True
    assert b.tripped is True
    assert b.tripped_at is not None


def test_evaluate_does_not_re_trip():
    """on_trip should fire exactly once per trip."""
    fires = []
    b = CircuitBreaker(
        name="test",
        check=lambda: True,
        on_trip=lambda name: fires.append(name),
    )
    b.evaluate()
    b.evaluate()  # second eval, still tripped
    assert fires == ["test"]  # exactly one fire


def test_resume_clears_trip():
    fired_resume = []
    b = CircuitBreaker(
        name="test",
        check=lambda: True,
        on_resume=lambda name: fired_resume.append(name),
    )
    b.evaluate()
    assert b.tripped is True
    b.resume()
    assert b.tripped is False
    assert b.tripped_at is None
    assert fired_resume == ["test"]


def test_resume_idempotent_on_untripped():
    fired = []
    b = CircuitBreaker(name="t", check=lambda: False, on_resume=lambda n: fired.append(n))
    b.resume()  # was never tripped
    assert fired == []  # on_resume should not fire


def test_check_exception_propagates():
    """D8: exceptions in check propagate to caller."""

    def boom():
        raise RuntimeError("metric source broken")

    b = CircuitBreaker(name="test", check=boom)
    with pytest.raises(RuntimeError, match="metric source broken"):
        b.evaluate()


def test_breaker_set_evaluate_all_returns_tripped_names():
    b1 = CircuitBreaker(name="rater_health", check=lambda: True)
    b2 = CircuitBreaker(name="follower_drop", check=lambda: False)
    s = BreakerSet([b1, b2])
    tripped = s.evaluate_all()
    assert "rater_health" in tripped
    assert "follower_drop" not in tripped


def test_breaker_set_any_tripped():
    b = CircuitBreaker(name="x", check=lambda: True)
    s = BreakerSet([b])
    s.evaluate_all()
    assert s.any_tripped() is True


def test_breaker_set_assert_clear_raises_open_error():
    """assert_clear() raises a NAMED exception so callers can distinguish."""
    b = CircuitBreaker(name="rater_health", check=lambda: True)
    s = BreakerSet([b])
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        s.assert_clear()
    assert "rater_health" in exc_info.value.tripped_names


def test_breaker_set_assert_clear_silent_when_clean():
    b = CircuitBreaker(name="x", check=lambda: False)
    s = BreakerSet([b])
    s.assert_clear()  # no exception


def test_breaker_set_resume_specific():
    b1 = CircuitBreaker(name="a", check=lambda: True)
    b2 = CircuitBreaker(name="b", check=lambda: True)
    s = BreakerSet([b1, b2])
    s.evaluate_all()
    s.resume("a")
    assert b1.tripped is False
    assert b2.tripped is True


def test_breaker_set_resume_unknown_raises():
    s = BreakerSet([CircuitBreaker(name="known", check=lambda: False)])
    with pytest.raises(KeyError):
        s.resume("unknown")


def test_breaker_set_resume_all():
    b1 = CircuitBreaker(name="a", check=lambda: True)
    b2 = CircuitBreaker(name="b", check=lambda: True)
    s = BreakerSet([b1, b2])
    s.evaluate_all()
    s.resume_all()
    assert b1.tripped is False
    assert b2.tripped is False


def test_open_error_carries_tripped_names():
    """The exception is queryable — caller can read which breakers tripped."""
    err = CircuitBreakerOpenError(tripped_names=["a", "b"])
    assert err.tripped_names == ["a", "b"]
    assert "a" in str(err) and "b" in str(err)


def test_caller_can_distinguish_breaker_open_from_other_errors():
    """The named-exception pattern makes scheduler logic clean."""
    b = CircuitBreaker(name="test", check=lambda: True)
    s = BreakerSet([b])

    def run_with_gate():
        s.assert_clear()
        raise RuntimeError("real failure")

    # This is how a scheduler distinguishes the two cases:
    try:
        run_with_gate()
    except CircuitBreakerOpenError as e:
        # Breaker is doing its job — log, skip, don't retry
        assert e.tripped_names == ["test"]
    except RuntimeError:
        pytest.fail("Should have raised CircuitBreakerOpenError first")
