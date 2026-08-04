"""Adapter implementing `apps.leave.application.ports.ApprovalRequestPort`
against `apps.approvals`'s already-composed public `ApprovalService`.

This is the one file in this module allowed to import `apps.approvals` —
and even here, only its public composition root
(`apps.approvals.interface.dependencies.build_approval_service`), never
that module's infrastructure or application internals directly. Same
discipline as `EmployeeServiceLookupAdapter` (this module's identical
adapter onto `apps.employees`).
"""
from __future__ import annotations

import uuid

from apps.approvals.application.dtos import CancelApprovalRequestForSubjectRequest, CreateApprovalRequestRequest
from apps.approvals.interface import dependencies as approvals_dependencies
from apps.leave.application.ports import ApprovalRequestPort

#: Fixed, module-owned constant — the one and only place this literal
#: string is written in apps.leave. `apps.leave.apps.py`'s chain-resolver
#: registration and `apps.leave.interface.event_handlers.handle_approval_decided`'s
#: filter both import this same constant, so the two ends of the contract
#: (which subject_type Leave registers a resolver for, and which
#: subject_type Leave listens for decisions on) can never drift apart.
SUBJECT_TYPE_LEAVE_REQUEST = "leave.leave_request"


class ApprovalServiceRequestAdapter(ApprovalRequestPort):
    def create_approval_request(
        self,
        *,
        subject_id: uuid.UUID,
        requested_by_employee_id: uuid.UUID,
        subject_summary: str,
        start_at_level: int = 1,
    ) -> None:
        approvals_dependencies.build_approval_service().create_approval_request(
            CreateApprovalRequestRequest(
                subject_type=SUBJECT_TYPE_LEAVE_REQUEST,
                subject_id=subject_id,
                requested_by_employee_id=requested_by_employee_id,
                subject_summary=subject_summary,
                start_at_level=start_at_level,
            )
        )

    def cancel_approval_request(self, *, subject_id: uuid.UUID, reason: str | None = None) -> None:
        # Round 17 item 2 — return value (`None` if nothing was open to
        # close) is intentionally ignored: `cancel_leave` calls this
        # unconditionally on every cancellation, and "there was nothing
        # open" is exactly as valid an outcome as "closed it."
        approvals_dependencies.build_approval_service().cancel_for_subject(
            CancelApprovalRequestForSubjectRequest(
                subject_type=SUBJECT_TYPE_LEAVE_REQUEST,
                subject_id=subject_id,
                reason=reason,
            )
        )
