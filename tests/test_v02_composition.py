"""Integration test: the v0.2 primitives compose end-to-end.

This is the wiring-diagram test from PHASE_A_DESIGN_2026-04-25.md.
Walks the full Drafter -> Rater -> Queue -> ApprovalChannel flow,
with MetricsEmitter observing and BreakerSet gating, using only Core
reference impls (no LLM, no Telegram, no Supabase).

If this passes, Scout and Presence have a working substrate to build on.
"""

import pytest

from pebbles.core.approval import (
    ApprovalAction,
    ApprovalDecision,
    MockApprovalChannel,
)
from pebbles.core.breakers import (
    BreakerSet,
    CircuitBreaker,
    CircuitBreakerOpenError,
)
from pebbles.core.metrics import InMemoryMetrics
from pebbles.core.principal import Principal
from pebbles.core.queue import InMemoryQueue, QueueStatus
from pebbles.core.rater import KeywordRater, RaterInput


@pytest.fixture
def song_principal():
    return Principal(
        id="song",
        name="Song",
        mode="ai_persona",
        children=["scout_song", "presence_song"],
        rubric={
            "positive_criteria": [
                {"id": "ai_perspective", "keywords": ["as an ai", "from where i sit"]},
                {"id": "specific_disagreement", "keywords": ["disagree", "actually"]},
            ],
            "hard_disqualifiers": [
                {"id": "sycophancy", "keywords": ["totally agree", "great point"]},
            ],
        },
    )


def test_full_pipeline_approve_path(song_principal):
    """Pipeline: rate -> enqueue -> send card -> simulate approve -> transition to approved."""
    # Wire primitives
    queue = InMemoryQueue()
    rater = KeywordRater(rubric=song_principal.rubric)
    metrics = InMemoryMetrics()
    approval = MockApprovalChannel()

    # Wire callback: ApprovalChannel decision -> Queue transition
    def on_decision(d: ApprovalDecision):
        if d.action == ApprovalAction.APPROVE:
            queue.transition(d.item_id, QueueStatus.APPROVED, approver=d.approver)
            metrics.emit(song_principal.id, "approved", metadata={"item_id": d.item_id})
        elif d.action == ApprovalAction.REJECT:
            queue.transition(d.item_id, QueueStatus.REJECTED, reject_reason=d.reason)
            metrics.emit(song_principal.id, "rejected", metadata={"item_id": d.item_id})
        elif d.action == ApprovalAction.EDIT:
            queue.transition(
                d.item_id, QueueStatus.EDITED,
                final_content=(d.edited_payload or {}).get("final_content"),
            )
            metrics.emit(song_principal.id, "edited", metadata={"item_id": d.item_id})

    approval.register_callback(on_decision)

    # 1. Rate a candidate
    candidate = {"draft_text": "From where I sit, I'd disagree with that framing"}
    rater_in = RaterInput(candidate=candidate, rubric=song_principal.rubric)
    rater_out = rater.rate(rater_in)
    metrics.emit(song_principal.id, "rated", value=rater_out.score)
    assert rater_out.score > 0  # passed at least one criterion

    # 2. Enqueue
    item_id = queue.enqueue(song_principal.id, {**candidate, "rater_score": rater_out.score})
    metrics.emit(song_principal.id, "enqueued", metadata={"item_id": item_id})

    # 3. Send to approval channel
    approval.send(item_id, candidate, approver="lucky")
    assert len(approval.sent) == 1

    # 4. Lucky taps approve
    approval.simulate_decision(item_id, ApprovalAction.APPROVE, approver="lucky")

    # 5. Verify queue transitioned
    item = queue.get(item_id)
    assert item["status"] == "approved"
    assert item["approver"] == "lucky"

    # 6. Verify metrics fan-in
    metric_types = {e["metric_type"] for e in metrics.events}
    assert {"rated", "enqueued", "approved"}.issubset(metric_types)


def test_full_pipeline_reject_path(song_principal):
    """A sycophantic draft should rate 0.0 (hard disqualifier) AND if it
    somehow made it to approval, lucky can reject it."""
    queue = InMemoryQueue()
    rater = KeywordRater(rubric=song_principal.rubric)

    rater_out = rater.rate(RaterInput(
        candidate={"draft_text": "totally agree, great point!"},
        rubric=song_principal.rubric,
    ))
    assert rater_out.score == 0.0  # hard disqualifier

    # Even so, downstream might enqueue it for visibility
    item_id = queue.enqueue(song_principal.id, {"draft_text": "..."})

    approval = MockApprovalChannel()

    def on_decision(d):
        if d.action == ApprovalAction.REJECT:
            queue.transition(d.item_id, QueueStatus.REJECTED, reject_reason=d.reason)

    approval.register_callback(on_decision)
    approval.simulate_decision(item_id, ApprovalAction.REJECT, reason="sycophancy hit")

    item = queue.get(item_id)
    assert item["status"] == "rejected"
    assert item["reject_reason"] == "sycophancy hit"


def test_breaker_gate_blocks_pipeline(song_principal):
    """When a breaker is tripped, assert_clear() raises CircuitBreakerOpenError
    and the scheduler skips the sweep."""
    queue = InMemoryQueue()
    rater_failure_count = 6  # exceeds threshold of 5
    breakers = BreakerSet([
        CircuitBreaker(
            name="rater_health",
            check=lambda: rater_failure_count > 5,
        ),
    ])

    def run_sweep():
        breakers.assert_clear()
        # If we got here, the breaker didn't trip — actual work happens
        queue.enqueue(song_principal.id, {})

    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        run_sweep()

    assert "rater_health" in exc_info.value.tripped_names
    # Pipeline did not run
    assert queue.list(song_principal.id) == []


def test_breaker_resume_unblocks_pipeline(song_principal):
    """After resume, the gate clears and the pipeline runs."""
    queue = InMemoryQueue()
    rater_failure_count = [6]  # mutable so we can reset
    breakers = BreakerSet([
        CircuitBreaker(
            name="rater_health",
            check=lambda: rater_failure_count[0] > 5,
        ),
    ])

    # First sweep: blocked
    with pytest.raises(CircuitBreakerOpenError):
        breakers.assert_clear()

    # Failure count drops, then resume
    rater_failure_count[0] = 0
    breakers.resume("rater_health")

    # Now sweep succeeds
    breakers.assert_clear()
    queue.enqueue(song_principal.id, {"text": "ok now"})
    assert len(queue.list(song_principal.id)) == 1


def test_metrics_observes_every_step_without_coupling(song_principal):
    """MetricsEmitter is fan-in: every other primitive can emit, but no primitive
    requires a MetricsEmitter to function."""
    queue = InMemoryQueue()  # no metrics dependency
    rater = KeywordRater(rubric=song_principal.rubric)  # no metrics dependency

    # Rater works fine without ever touching metrics
    out = rater.rate(RaterInput(
        candidate={"draft_text": "as an AI, I disagree"},
        rubric=song_principal.rubric,
    ))
    assert out.score > 0

    # Queue works fine without ever touching metrics
    item_id = queue.enqueue(song_principal.id, {})
    assert queue.get(item_id) is not None
