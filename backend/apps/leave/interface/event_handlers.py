"""Subscribers for events this module reacts to:
`apps.employees.domain.events.EmployeeCreated` and
`apps.approvals.domain.events.ApprovalDecided`.

Registered by `apps/leave/apps.py`'s `ready()` hook. Lives in the interface
layer (not infrastructure) deliberately: these functions play the same
composition-root role `interface/dependencies.py` does — each needs an
already-composed service, which is exactly the "wires application and
infrastructure together" responsibility that belongs at this layer, not
inside infrastructure itself (infrastructure code must not depend on how a
whole service is composed).
"""
from __future__ import annotations

import logging
from datetime import date

from apps.approvals.domain.enums import ApprovalStatus
from apps.approvals.domain.events import ApprovalDecided
from apps.employees.domain.events import EmployeeCreated
from apps.leave.application.dtos import ApproveLeaveRequest, RejectLeaveRequest
from apps.leave.infrastructure.approval_request_adapter import SUBJECT_TYPE_LEAVE_REQUEST
from apps.leave.interface import dependencies

logger = logging.getLogger(__name__)


def handle_employee_created(event: EmployeeCreated) -> None:
    """Provisions one `LeaveBalance` row per currently-active `LeaveType`
    for the new employee, for the current calendar year, seeded from each
    type's `default_annual_days`. Idempotent (see
    `LeaveBalanceService.provision_initial_balance`) — safe to run more than
    once for the same employee without creating duplicate rows.
    """
    from apps.leave.infrastructure.repositories import DjangoLeaveTypeRepository

    balance_service = dependencies.build_leave_balance_service()
    year = date.today().year
    for leave_type in DjangoLeaveTypeRepository().list_active():
        balance_service.provision_initial_balance(employee_id=event.employee_id, leave_type=leave_type, year=year)

    logger.info("Provisioned initial leave balances for new employee=%s (year=%s)", event.employee_id, year)


def handle_approval_decided(event: ApprovalDecided) -> None:
    """Reacts to the generic Approval Engine's `ApprovalDecided` event by
    finally calling `LeaveRequestService.approve()`/`.reject()` — the two
    methods Phase 8 built, unit-tested, and left uncalled specifically for
    this moment (see `apps.leave.domain.entities.LeaveRequest.approve`'s
    docstring: "Approval module extension point").

    Filters on `subject_type` first: this event fires for every subject
    module using the Approval Engine, not just Leave, and Leave must ignore
    every event that isn't its own — the same discipline any fan-out
    subscriber needs (compare to how a future Notifications module would
    subscribe to this same event and never filter at all, since it cares
    about every subject).

    `event.decided_by_employee_id` becomes `LeaveRequestService.approve`'s
    `approved_by` — that field predates Phase 9 and its own docstring/DB
    comment still says "logical reference to identity_users.id" (written
    before this module's approval flow was designed); Phase 9 is what
    finally defines its real semantics: the deciding manager's *employee*
    id, resolved from their Telegram account, never an identity.User id
    (managers decide via Telegram, which has no identity.User concept at
    all). The column itself is a plain, unconstrained UUID either way, so
    no migration is needed to correct that stale comment.
    """
    if event.subject_type != SUBJECT_TYPE_LEAVE_REQUEST:
        return

    request_service = dependencies.build_leave_request_service()
    if event.final_status == ApprovalStatus.APPROVED.value:
        request_service.approve(
            ApproveLeaveRequest(
                leave_request_id=event.subject_id,
                approved_by=event.decided_by_employee_id,
                comments=event.comments,
            )
        )
    elif event.final_status == ApprovalStatus.REJECTED.value:
        request_service.reject(
            RejectLeaveRequest(leave_request_id=event.subject_id, comments=event.comments)
        )
    else:
        # Defensive only — ApprovalDecided.final_status is always
        # ApprovalStatus.APPROVED.value or ApprovalStatus.REJECTED.value
        # (see apps.approvals.application.services.approval_service).
        logger.warning(
            "Unexpected ApprovalDecided.final_status=%r for leave_request=%s — ignoring.",
            event.final_status,
            event.subject_id,
        )
