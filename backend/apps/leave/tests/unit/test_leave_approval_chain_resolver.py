"""Unit tests for `LeaveApprovalChainResolver` — Phase 13 added a second
(HR/Admin, permission-based) level on top of Phase 9's single manager
level. Every dependency is a hand-rolled fake, no Django, no database, same
discipline as `test_leave_validation_service.py`.
"""
from __future__ import annotations

import uuid

from apps.approvals.domain.enums import ApprovalChannel
from apps.approvals.domain.value_objects import ApproverAssignment
from apps.leave.infrastructure.leave_approval_chain_resolver import LeaveApprovalChainResolver

_SUBJECT_TYPE = "leave.leave_request"


class FakeEmployeeLookupPort:
    def __init__(self, managers: dict[uuid.UUID, uuid.UUID | None] | None = None):
        self._managers = managers or {}

    def get_manager_employee_id(self, employee_id):
        return self._managers.get(employee_id)


def test_level_1_resolves_to_a_dual_mode_assignment_for_the_applicants_manager() -> None:
    applicant, manager = uuid.uuid4(), uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: manager}))

    result = resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=1
    )

    assert result == ApproverAssignment.for_employee_or_permission_by_channel(
        employee_id=manager,
        permission_code="approvals.level1_approve",
        permission_required_for_channel=ApprovalChannel.WEB.value,
    )


def test_level_1_is_decidable_by_the_manager_via_telegram_identity() -> None:
    """Approval Workflow Changes v2: 'Manager approval can be completed
    through Telegram' — via Telegram, identity alone still governs, exactly
    as since Phase 9."""
    applicant, manager = uuid.uuid4(), uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: manager}))

    result = resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=1
    )

    assert result is not None
    assert result.employee_id == manager
    assert result.restricted_to_channel is None  # no longer Telegram-only


def test_level_1_web_decision_is_governed_by_the_level1_approve_permission() -> None:
    """Approval Workflow Changes v2: 'HR system Level 1 approval must be
    controlled by role permissions... only users with Level 1 approval
    permission can approve Level 1 from the HR system.'"""
    applicant, manager = uuid.uuid4(), uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: manager}))

    result = resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=1
    )

    assert result is not None
    assert result.permission_code == "approvals.level1_approve"
    assert result.permission_required_for_channel == ApprovalChannel.WEB.value
    assert result.is_dual_mode


def test_level_1_returns_none_when_the_applicant_has_no_manager() -> None:
    applicant = uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: None}))

    result = resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=1
    )

    assert result is None


def test_level_2_resolves_to_anyone_holding_level2_approve() -> None:
    """Approval Workflow Changes v2: level 2's permission code is now the
    engine-level `approvals.level2_approve` — a SEPARATE permission from
    `leave.manage_leave`, which continues to gate Leave's own management
    screens and has nothing to do with deciding an approval step."""
    applicant = uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: uuid.uuid4()}))

    result = resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=2
    )

    assert result == ApproverAssignment.for_permission(
        "approvals.level2_approve",
        requester_notification_message=(
            "Your manager has approved your leave request. It is now awaiting HR processing."
        ),
        restricted_to_channel=ApprovalChannel.WEB.value,
    )


def test_level_2_is_restricted_to_the_web_channel() -> None:
    """Approval Workflow Changes review round: 'Level 2 approval should
    always be completed from the HR system.' — an HR/Admin employee who
    happens to also be linked to Telegram still cannot decide this level
    from there."""
    applicant = uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: uuid.uuid4()}))

    result = resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=2
    )

    assert result is not None
    assert result.restricted_to_channel == ApprovalChannel.WEB.value


def test_level_2_supplies_the_manager_approved_awaiting_hr_message() -> None:
    """Leave review round: the applicant's advance notification carries this
    exact wording, not a generic engine fallback — see
    `ApproverAssignment.requester_notification_message`'s docstring."""
    applicant = uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: uuid.uuid4()}))

    result = resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=2
    )

    assert result is not None
    assert (
        result.requester_notification_message
        == "Your manager has approved your leave request. It is now awaiting HR processing."
    )


def test_level_3_and_beyond_returns_none_chain_complete() -> None:
    applicant = uuid.uuid4()
    resolver = LeaveApprovalChainResolver(FakeEmployeeLookupPort({applicant: uuid.uuid4()}))

    assert resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=3
    ) is None
    assert resolver.resolve_next_approver(
        subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=applicant, level=4
    ) is None
