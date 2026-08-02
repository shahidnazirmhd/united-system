"""Unit tests for auth/approval_decision.py's ApprovalDecisionService — the
one-step "add an optional comment" flow following an Approve/Reject tap.
Mirrors tests/unit/test_leave_application.py's discipline exactly."""
from __future__ import annotations

import pytest

from src.api_client.endpoints.approvals import ApprovalRequest
from src.auth.approval_decision import DECISION_APPROVE, DECISION_REJECT, ApprovalDecisionService
from src.errors import NoApprovalDecisionInProgressError
from tests.fakes import FakeApprovalsEndpoint, FakeRedis

_DECIDED_REQUEST = ApprovalRequest(
    id="req-1", subject_type="leave.leave_request", subject_id="leave-req-1", requested_by_employee_id="emp-1",
    subject_summary="Annual Leave: 3 days", status="approved", current_level=1,
)


def _service(approvals=None, redis=None) -> ApprovalDecisionService:
    return ApprovalDecisionService(approvals or FakeApprovalsEndpoint(), redis or FakeRedis())


async def test_start_records_pending_state():
    service = _service()

    await service.start(telegram_user_id=42, approval_request_id="req-1", decision=DECISION_APPROVE)

    state = await service.get_state(42)
    assert state.approval_request_id == "req-1"
    assert state.decision == DECISION_APPROVE
    assert await service.is_active(42) is True


async def test_is_active_false_when_nothing_pending():
    service = _service()
    assert await service.is_active(42) is False


async def test_submit_comment_calls_decide_with_typed_text():
    approvals = FakeApprovalsEndpoint(decide_result=_DECIDED_REQUEST)
    service = _service(approvals=approvals)
    await service.start(telegram_user_id=42, approval_request_id="req-1", decision=DECISION_APPROVE)

    result = await service.submit_comment(42, "Enjoy your trip")

    assert result is _DECIDED_REQUEST
    assert approvals.decide_calls[0] == {
        "telegram_user_id": 42,
        "approval_request_id": "req-1",
        "decision": DECISION_APPROVE,
        "comments": "Enjoy your trip",
    }


async def test_submit_comment_treats_skip_as_no_comment():
    approvals = FakeApprovalsEndpoint(decide_result=_DECIDED_REQUEST)
    service = _service(approvals=approvals)
    await service.start(telegram_user_id=42, approval_request_id="req-1", decision=DECISION_REJECT)

    await service.submit_comment(42, "skip")

    assert approvals.decide_calls[0]["comments"] is None


async def test_submit_comment_clears_state_even_when_decide_raises():
    from tests.fakes import make_hrms_error

    approvals = FakeApprovalsEndpoint(raise_on_decide=make_hrms_error("approval_request_not_pending", status_code=409))
    service = _service(approvals=approvals)
    await service.start(telegram_user_id=42, approval_request_id="req-1", decision=DECISION_APPROVE)

    with pytest.raises(Exception):
        await service.submit_comment(42, "skip")

    assert await service.is_active(42) is False


async def test_submit_comment_raises_when_nothing_pending():
    service = _service()

    with pytest.raises(NoApprovalDecisionInProgressError):
        await service.submit_comment(42, "skip")


async def test_cancel_clears_pending_state():
    service = _service()
    await service.start(telegram_user_id=42, approval_request_id="req-1", decision=DECISION_APPROVE)

    await service.cancel(42)

    assert await service.is_active(42) is False
