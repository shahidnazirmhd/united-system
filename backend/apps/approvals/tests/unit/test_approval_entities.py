"""Unit tests for the Approval Engine's domain entities — pure Python, no
Django, no database. Same discipline as apps/leave/tests/unit/test_leave_entities.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.approvals.domain.entities import ApprovalRequest, ApprovalStep
from apps.approvals.domain.enums import ApprovalStatus, ApprovalStepStatus
from apps.approvals.domain.exceptions import ApprovalRequestNotPendingError, ApprovalStepNotPendingError


def _step(**overrides) -> ApprovalStep:
    return ApprovalStep(
        id=overrides.pop("id", uuid.uuid4()),
        approval_request_id=overrides.pop("approval_request_id", uuid.uuid4()),
        level=overrides.pop("level", 1),
        approver_employee_id=overrides.pop("approver_employee_id", uuid.uuid4()),
        status=overrides.pop("status", ApprovalStepStatus.PENDING),
    )


def _request(**overrides) -> ApprovalRequest:
    return ApprovalRequest(
        id=overrides.pop("id", uuid.uuid4()),
        subject_type=overrides.pop("subject_type", "leave.leave_request"),
        subject_id=overrides.pop("subject_id", uuid.uuid4()),
        requested_by_employee_id=overrides.pop("requested_by_employee_id", uuid.uuid4()),
        subject_summary=overrides.pop("subject_summary", "Annual Leave: 2026-09-01 -> 2026-09-03 (3 days)"),
        status=overrides.pop("status", ApprovalStatus.PENDING),
        current_level=overrides.pop("current_level", 1),
    )


# --- ApprovalStep ---------------------------------------------------------


def test_step_approve_transitions_pending_to_approved() -> None:
    step = _step()
    decider_id = uuid.uuid4()

    approved = step.approve(decided_at=datetime.now(timezone.utc), decided_by_employee_id=decider_id, comments="Looks good")

    assert approved.status == ApprovalStepStatus.APPROVED
    assert approved.comments == "Looks good"
    assert approved.decided_at is not None
    assert approved.decided_by_employee_id == decider_id
    assert approved.id == step.id  # same identity


def test_step_reject_transitions_pending_to_rejected() -> None:
    step = _step()
    decider_id = uuid.uuid4()

    rejected = step.reject(
        decided_at=datetime.now(timezone.utc), decided_by_employee_id=decider_id, comments="Not enough coverage"
    )

    assert rejected.status == ApprovalStepStatus.REJECTED
    assert rejected.comments == "Not enough coverage"
    assert rejected.decided_by_employee_id == decider_id


def test_step_approve_raises_when_already_decided() -> None:
    step = _step(status=ApprovalStepStatus.APPROVED)

    with pytest.raises(ApprovalStepNotPendingError):
        step.approve(decided_at=datetime.now(timezone.utc), decided_by_employee_id=uuid.uuid4())


def test_step_reject_raises_when_already_decided() -> None:
    step = _step(status=ApprovalStepStatus.REJECTED)

    with pytest.raises(ApprovalStepNotPendingError):
        step.reject(decided_at=datetime.now(timezone.utc), decided_by_employee_id=uuid.uuid4())


def test_step_cancel_transitions_pending_to_cancelled_with_no_decider() -> None:
    """Round 17 item 2 — unlike approve()/reject(), nobody decided this
    step; it was closed because the subject module cancelled the
    underlying request."""
    step = _step()

    cancelled = step.cancel(decided_at=datetime.now(timezone.utc), comments="Plans changed")

    assert cancelled.status == ApprovalStepStatus.CANCELLED
    assert cancelled.comments == "Plans changed"
    assert cancelled.decided_by_employee_id is None
    assert cancelled.id == step.id


def test_step_cancel_raises_when_already_decided() -> None:
    step = _step(status=ApprovalStepStatus.APPROVED)

    with pytest.raises(ApprovalStepNotPendingError):
        step.cancel(decided_at=datetime.now(timezone.utc))


# --- ApprovalStep.is_decidable_by — dual-mode (Approval Workflow Changes v2) ---


def test_is_decidable_by_single_employee_mode_ignores_channel() -> None:
    manager_id = uuid.uuid4()
    step = _step(approver_employee_id=manager_id)

    assert step.is_decidable_by(acting_employee_id=manager_id, held_permission_codes=frozenset(), channel="web")
    assert step.is_decidable_by(acting_employee_id=manager_id, held_permission_codes=frozenset(), channel="telegram")
    assert not step.is_decidable_by(
        acting_employee_id=uuid.uuid4(), held_permission_codes=frozenset(), channel="web"
    )


def test_is_decidable_by_single_permission_mode_ignores_channel() -> None:
    step = ApprovalStep(
        id=uuid.uuid4(),
        approval_request_id=uuid.uuid4(),
        level=2,
        approver_employee_id=None,
        approver_permission_code="approvals.level2_approve",
    )

    assert step.is_decidable_by(
        acting_employee_id=uuid.uuid4(), held_permission_codes=frozenset({"approvals.level2_approve"}), channel="web"
    )
    assert not step.is_decidable_by(acting_employee_id=uuid.uuid4(), held_permission_codes=frozenset(), channel="web")


def test_is_decidable_by_dual_mode_uses_identity_off_the_permission_channel() -> None:
    manager_id = uuid.uuid4()
    step = ApprovalStep(
        id=uuid.uuid4(),
        approval_request_id=uuid.uuid4(),
        level=1,
        approver_employee_id=manager_id,
        approver_permission_code="approvals.level1_approve",
        permission_required_for_channel="web",
    )

    # Telegram: identity governs, regardless of permission.
    assert step.is_decidable_by(acting_employee_id=manager_id, held_permission_codes=frozenset(), channel="telegram")
    assert not step.is_decidable_by(
        acting_employee_id=uuid.uuid4(),
        held_permission_codes=frozenset({"approvals.level1_approve"}),
        channel="telegram",
    )


def test_is_decidable_by_dual_mode_uses_permission_on_the_named_channel() -> None:
    manager_id = uuid.uuid4()
    other_holder_id = uuid.uuid4()
    step = ApprovalStep(
        id=uuid.uuid4(),
        approval_request_id=uuid.uuid4(),
        level=1,
        approver_employee_id=manager_id,
        approver_permission_code="approvals.level1_approve",
        permission_required_for_channel="web",
    )

    # Web: permission governs, even for the manager.
    assert step.is_decidable_by(
        acting_employee_id=other_holder_id,
        held_permission_codes=frozenset({"approvals.level1_approve"}),
        channel="web",
    )
    assert not step.is_decidable_by(acting_employee_id=manager_id, held_permission_codes=frozenset(), channel="web")


def test_approve_and_reject_carry_forward_dual_mode_fields() -> None:
    manager_id = uuid.uuid4()
    decider_id = uuid.uuid4()
    step = ApprovalStep(
        id=uuid.uuid4(),
        approval_request_id=uuid.uuid4(),
        level=1,
        approver_employee_id=manager_id,
        approver_permission_code="approvals.level1_approve",
        permission_required_for_channel="web",
        restricted_to_channel=None,
    )

    approved = step.approve(decided_at=datetime.now(timezone.utc), decided_by_employee_id=decider_id)

    assert approved.approver_employee_id == manager_id
    assert approved.approver_permission_code == "approvals.level1_approve"
    assert approved.permission_required_for_channel == "web"
    assert approved.decided_by_employee_id == decider_id


# --- ApprovalRequest -------------------------------------------------------


def test_request_advance_to_level_stays_pending_at_new_level() -> None:
    request = _request(current_level=1)

    advanced = request.advance_to_level(2)

    assert advanced.status == ApprovalStatus.PENDING
    assert advanced.current_level == 2


def test_request_mark_approved_transitions_pending_to_approved() -> None:
    request = _request()

    approved = request.mark_approved()

    assert approved.status == ApprovalStatus.APPROVED


def test_request_mark_rejected_transitions_pending_to_rejected() -> None:
    request = _request()

    rejected = request.mark_rejected()

    assert rejected.status == ApprovalStatus.REJECTED


def test_request_advance_to_level_raises_when_not_pending() -> None:
    request = _request(status=ApprovalStatus.APPROVED)

    with pytest.raises(ApprovalRequestNotPendingError):
        request.advance_to_level(2)


def test_request_mark_approved_raises_when_already_rejected() -> None:
    request = _request(status=ApprovalStatus.REJECTED)

    with pytest.raises(ApprovalRequestNotPendingError):
        request.mark_approved()


def test_request_mark_rejected_raises_when_already_approved() -> None:
    request = _request(status=ApprovalStatus.APPROVED)

    with pytest.raises(ApprovalRequestNotPendingError):
        request.mark_rejected()


def test_request_mark_cancelled_transitions_pending_to_cancelled() -> None:
    """Round 17 item 2 — a distinct terminal status from REJECTED: the
    subject module withdrew its own request, no approver rejected it."""
    request = _request()

    cancelled = request.mark_cancelled()

    assert cancelled.status == ApprovalStatus.CANCELLED


def test_request_mark_cancelled_raises_when_already_rejected() -> None:
    request = _request(status=ApprovalStatus.REJECTED)

    with pytest.raises(ApprovalRequestNotPendingError):
        request.mark_cancelled()


def test_request_mark_cancelled_raises_when_already_approved() -> None:
    request = _request(status=ApprovalStatus.APPROVED)

    with pytest.raises(ApprovalRequestNotPendingError):
        request.mark_cancelled()
