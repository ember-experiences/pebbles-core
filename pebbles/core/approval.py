"""ApprovalChannel Protocol — generic 'send a thing to a human, get back approve/edit/reject'.

The channel owns rendering (channel-specific UI) and event-routing (channel-specific
event source). Core specifies the contract; impls live with their dependencies
(TelegramApprovalChannel in pebbles-presence, SlackApprovalChannel future, etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional, Protocol


class ApprovalAction(str, Enum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    EXPIRE = "expire"  # auto-expired after timeout


@dataclass
class ApprovalDecision:
    """The outcome of an approval round-trip."""

    item_id: str
    action: ApprovalAction
    approver: str  # who decided (e.g. "lucky")
    reason: Optional[str] = None  # for reject
    edited_payload: Optional[dict] = None  # for edit
    decided_at: Optional[str] = None  # ISO timestamp

    def __post_init__(self):
        if self.decided_at is None:
            self.decided_at = datetime.now(timezone.utc).isoformat()


class ApprovalChannel(Protocol):
    """Protocol for human-in-loop approval channels."""

    def send(self, item_id: str, payload: dict, approver: str) -> bool:
        """Send an approval card. Returns True if delivery succeeded.

        The channel renders the card in its native format (Markdown for Telegram,
        blocks for Slack, HTML for email). Buttons / callbacks are channel-specific.
        """
        ...

    def register_callback(
        self, on_decision: Callable[[ApprovalDecision], None]
    ) -> None:
        """Register a handler invoked when the approver decides.

        The channel is responsible for:
        - matching button taps / replies back to item_id
        - constructing ApprovalDecision
        - invoking on_decision(decision)

        Multiple callbacks can be registered; channel calls all of them.
        """
        ...


class MockApprovalChannel:
    """Reference impl. For tests.

    Captures all sent cards; lets tests trigger decisions programmatically.
    """

    def __init__(self):
        self.sent: list[dict] = []
        self._callbacks: list[Callable[[ApprovalDecision], None]] = []

    def send(self, item_id, payload, approver):
        self.sent.append({"item_id": item_id, "payload": dict(payload), "approver": approver})
        return True

    def register_callback(self, on_decision):
        self._callbacks.append(on_decision)

    def simulate_decision(
        self,
        item_id: str,
        action: ApprovalAction,
        approver: str = "test_approver",
        reason: Optional[str] = None,
        edited_payload: Optional[dict] = None,
    ) -> None:
        """Test helper — fire a decision through registered callbacks."""
        decision = ApprovalDecision(
            item_id=item_id,
            action=action,
            approver=approver,
            reason=reason,
            edited_payload=edited_payload,
        )
        for cb in self._callbacks:
            cb(decision)
