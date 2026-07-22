"""Unit tests for domain entity behaviour — no Django, no fakes needed
beyond the entities themselves. Covers the status state machine
(cancel/approve/reject) and the balance arithmetic helpers.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.leave.domain.entities import LeaveBalance, LeaveRequest
from apps.leave.domain.enums import LeaveRequestStatus
from apps.leave.domain.exceptions import LeaveRequestNotCancellableError, LeaveRequestNotInPendingStateError
from shared_kernel.domain.value_objects import DateRange


def _request(status: LeaveRequestStatus = LeaveRequestStatus.PENDING) -> LeaveRequest:
    return LeaveRequest(
        id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        leave_type_id=uuid.uuid4(),
        date_range=DateRange(start_date=date(2026, 8, 1), end_date=date(2026, 8, 3)),
        status=status,
    )


def test_total_days_is_inclusive_of_both_endpoints() -> None:
    request = _request()
    assert request.total_days == Decimal(3)


def test_cancel_pending_request_succeeds() -> None:
    request = _request(LeaveRequestStatus.PENDING)
    now = datetime.now(timezone.utc)

    cancelled = request.cancel(cancelled_at=now, reason="Change of plans")

    assert cancelled.status == LeaveRequestStatus.CANCELLED
    assert cancelled.cancelled_at == now
    assert cancelled.cancellation_reason == "Change of plans"


def test_cancel_approved_request_succeeds() -> None:
    request = _request(LeaveRequestStatus.APPROVED)

    cancelled = request.cancel(cancelled_at=datetime.now(timezone.utc), reason=None)

    assert cancelled.status == LeaveRequestStatus.CANCELLED


@pytest.mark.parametrize("status", [LeaveRequestStatus.REJECTED, LeaveRequestStatus.CANCELLED, LeaveRequestStatus.DRAFT])
def test_cancel_raises_when_not_cancellable(status: LeaveRequestStatus) -> None:
    request = _request(status)

    with pytest.raises(LeaveRequestNotCancellableError):
        request.cancel(cancelled_at=datetime.now(timezone.utc), reason=None)


def test_approve_pending_request_succeeds() -> None:
    request = _request(LeaveRequestStatus.PENDING)
    approver_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    approved = request.approve(approved_by=approver_id, decided_at=now, comments="Looks good")

    assert approved.status == LeaveRequestStatus.APPROVED
    assert approved.approved_by == approver_id
    assert approved.decided_at == now
    assert approved.decision_comments == "Looks good"


def test_approve_raises_when_not_pending() -> None:
    request = _request(LeaveRequestStatus.APPROVED)

    with pytest.raises(LeaveRequestNotInPendingStateError):
        request.approve(approved_by=uuid.uuid4(), decided_at=datetime.now(timezone.utc))


def test_reject_pending_request_succeeds() -> None:
    request = _request(LeaveRequestStatus.PENDING)

    rejected = request.reject(decided_at=datetime.now(timezone.utc), comments="Insufficient coverage")

    assert rejected.status == LeaveRequestStatus.REJECTED
    assert rejected.decision_comments == "Insufficient coverage"


def test_reject_raises_when_not_pending() -> None:
    request = _request(LeaveRequestStatus.CANCELLED)

    with pytest.raises(LeaveRequestNotInPendingStateError):
        request.reject(decided_at=datetime.now(timezone.utc))


def _balance(**overrides) -> LeaveBalance:
    return LeaveBalance(
        id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        leave_type_id=uuid.uuid4(),
        year=2026,
        entitled_days=overrides.get("entitled_days", Decimal("20")),
        used_days=overrides.get("used_days", Decimal("5")),
        carried_forward_days=overrides.get("carried_forward_days", Decimal("2")),
    )


def test_available_days_sums_entitled_and_carried_forward_minus_used() -> None:
    balance = _balance(entitled_days=Decimal("20"), used_days=Decimal("5"), carried_forward_days=Decimal("2"))
    assert balance.available_days == Decimal("17")


def test_increase_used_days_returns_new_instance_without_mutating_original() -> None:
    balance = _balance(used_days=Decimal("5"))

    updated = balance.increase_used_days(Decimal("3"))

    assert updated.used_days == Decimal("8")
    assert balance.used_days == Decimal("5")  # original untouched


def test_decrease_used_days_floors_at_zero() -> None:
    balance = _balance(used_days=Decimal("2"))

    updated = balance.decrease_used_days(Decimal("10"))

    assert updated.used_days == Decimal("0")
