"""Transient conversation state for the one-step "add an optional comment"
flow that follows tapping Approve/Reject on an approval request — the
Approvals-module equivalent of `auth/leave_application.py`'s multi-step
state, simplified to a single step since a decision only ever needs one
more piece of input (the optional comment) before it's submitted.

State lives in Redis, keyed by `telegram_user_id`, short-lived — same
"a stalled conversation should not block starting fresh" reasoning as
`auth/leave_application.py`'s identical TTL choice, just a shorter window
since this flow is a single free-text reply, not several date pickers.

This service does no business validation at all — it only shapes and
carries the decision forward. Every real business rule (must be the
assigned approver, request must still be pending, ...) is enforced by the
backend when `submit_comment()` finally calls `ApprovalsEndpoint.decide()`.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from src.errors import NoApprovalDecisionInProgressError
from src.logging_config import log_event

if TYPE_CHECKING:
    import redis.asyncio as redis

    from src.api_client.endpoints.approvals import ApprovalRequest, ApprovalsEndpoint

logger = logging.getLogger(__name__)

_KEY_PREFIX = "telegram_gateway:approval_decision:"
_DECISION_STATE_TTL = timedelta(minutes=10)

DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"


@dataclass(frozen=True)
class ApprovalDecisionState:
    approval_request_id: str
    decision: str


class ApprovalDecisionService:
    def __init__(self, approvals: ApprovalsEndpoint, redis_client: redis.Redis) -> None:
        self._approvals = approvals
        self._redis = redis_client

    @staticmethod
    def _key(telegram_user_id: int) -> str:
        return f"{_KEY_PREFIX}{telegram_user_id}"

    async def start(self, *, telegram_user_id: int, approval_request_id: str, decision: str) -> None:
        """Called the instant Approve/Reject is tapped — awaits the
        optional comment next."""
        state = ApprovalDecisionState(approval_request_id=approval_request_id, decision=decision)
        await self._redis.set(
            self._key(telegram_user_id),
            json.dumps({"approval_request_id": state.approval_request_id, "decision": state.decision}),
            ex=int(_DECISION_STATE_TTL.total_seconds()),
        )
        log_event(
            logger,
            logging.INFO,
            "approval_decision_started",
            telegram_user_id=telegram_user_id,
            approval_request_id=approval_request_id,
            decision=decision,
        )

    async def get_state(self, telegram_user_id: int) -> ApprovalDecisionState | None:
        raw = await self._redis.get(self._key(telegram_user_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return ApprovalDecisionState(**data)

    async def is_active(self, telegram_user_id: int) -> bool:
        return await self._redis.exists(self._key(telegram_user_id)) == 1

    async def submit_comment(self, telegram_user_id: int, text: str) -> ApprovalRequest:
        """Final step: submits the decision (with or without a comment) to
        the backend. On ANY outcome the pending state is cleared — same
        "don't let a rejected/failed decision silently retry against stale
        state" discipline as `LeaveApplicationService.submit`."""
        state = await self.get_state(telegram_user_id)
        if state is None:
            raise NoApprovalDecisionInProgressError()
        comments = None if text.strip().lower() == "skip" else text.strip()
        try:
            result = await self._approvals.decide(
                telegram_user_id=telegram_user_id,
                approval_request_id=state.approval_request_id,
                decision=state.decision,
                comments=comments,
            )
        finally:
            await self._redis.delete(self._key(telegram_user_id))
        log_event(
            logger,
            logging.INFO,
            "approval_decision_submitted",
            telegram_user_id=telegram_user_id,
            approval_request_id=state.approval_request_id,
            decision=state.decision,
        )
        return result

    async def cancel(self, telegram_user_id: int) -> None:
        await self._redis.delete(self._key(telegram_user_id))
