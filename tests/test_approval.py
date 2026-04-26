"""Tests for pebbles.core.approval."""

from pebbles.core.approval import (
    ApprovalAction,
    ApprovalDecision,
    MockApprovalChannel,
)


def test_decision_auto_timestamps_if_missing():
    d = ApprovalDecision(item_id="x", action=ApprovalAction.APPROVE, approver="lucky")
    assert d.decided_at is not None
    assert "T" in d.decided_at  # ISO format


def test_decision_preserves_explicit_timestamp():
    d = ApprovalDecision(
        item_id="x",
        action=ApprovalAction.APPROVE,
        approver="lucky",
        decided_at="2026-01-01T00:00:00+00:00",
    )
    assert d.decided_at == "2026-01-01T00:00:00+00:00"


def test_mock_channel_send_records():
    ch = MockApprovalChannel()
    assert ch.send("item-1", {"draft": "hello"}, approver="lucky") is True
    assert len(ch.sent) == 1
    assert ch.sent[0]["item_id"] == "item-1"
    assert ch.sent[0]["payload"] == {"draft": "hello"}
    assert ch.sent[0]["approver"] == "lucky"


def test_mock_channel_callback_fires():
    ch = MockApprovalChannel()
    decisions: list[ApprovalDecision] = []
    ch.register_callback(lambda d: decisions.append(d))

    ch.simulate_decision("item-1", ApprovalAction.APPROVE, approver="lucky")
    assert len(decisions) == 1
    assert decisions[0].item_id == "item-1"
    assert decisions[0].action == ApprovalAction.APPROVE


def test_mock_channel_multiple_callbacks_all_fire():
    ch = MockApprovalChannel()
    seen_a, seen_b = [], []
    ch.register_callback(lambda d: seen_a.append(d.item_id))
    ch.register_callback(lambda d: seen_b.append(d.item_id))

    ch.simulate_decision("x", ApprovalAction.REJECT)
    assert seen_a == ["x"]
    assert seen_b == ["x"]


def test_mock_channel_carries_reject_reason():
    ch = MockApprovalChannel()
    decisions: list[ApprovalDecision] = []
    ch.register_callback(decisions.append)
    ch.simulate_decision("x", ApprovalAction.REJECT, reason="too didactic")
    assert decisions[0].reason == "too didactic"


def test_mock_channel_carries_edited_payload():
    ch = MockApprovalChannel()
    decisions: list[ApprovalDecision] = []
    ch.register_callback(decisions.append)
    ch.simulate_decision(
        "x",
        ApprovalAction.EDIT,
        edited_payload={"final_content": "edited", "semantic_edit_distance": 0.18},
    )
    assert decisions[0].edited_payload == {
        "final_content": "edited",
        "semantic_edit_distance": 0.18,
    }
