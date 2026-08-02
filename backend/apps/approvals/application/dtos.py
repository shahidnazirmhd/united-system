"""Input/output DTOs for the Approval Engine's application services.

Interface-layer serializers convert HTTP request/response JSON to/from
these — services never see a DRF Request/Response object, matching every
other module's `application/dtos.py` convention exactly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class CreateApprovalRequestRequest:
    subject_type: str
    subject_id: uuid.UUID
    requested_by_employee_id: uuid.UUID
    subject_summary: str


@dataclass(frozen=True)
class DecideApprovalRequest:
    approval_request_id: uuid.UUID
    acting_employee_id: uuid.UUID
    decision: str  # "approve" | "reject" — see application/services/approval_service.py's DECISION_* constants
    # Which surface this call arrived through
    # (`apps.approvals.domain.enums.ApprovalChannel.WEB`/`.TELEGRAM`) —
    # required, never inferred or defaulted, since every real caller (the
    # two `Decide*View`s in interface/views.py) always knows exactly which
    # one it is. Checked against the current step's own
    # `restricted_to_channel` (Approval Workflow Changes review round) —
    # see `ApprovalService.decide`.
    channel: str
    comments: str | None = None


@dataclass(frozen=True)
class CancelApprovalRequestForSubjectRequest:
    """Round 17 item 2 — input to `ApprovalService.cancel_for_subject`.
    Mirrors `CreateApprovalRequestRequest`'s shape: `subject_type`/
    `subject_id` identify which subject's open approval request to close;
    the calling module's own adapter fixes `subject_type` to its own
    constant, exactly like `ApprovalServiceRequestAdapter.create_approval_request`
    already does for creation."""

    subject_type: str
    subject_id: uuid.UUID
    reason: str | None = None


@dataclass(frozen=True)
class ApprovalStepResponse:
    id: uuid.UUID
    approval_request_id: uuid.UUID
    level: int
    # Exactly one of these two is populated — see
    # apps.approvals.domain.value_objects.ApproverAssignment.
    approver_employee_id: uuid.UUID | None
    approver_permission_code: str | None
    # Which channel this step may be decided from, or `None` for
    # unrestricted — see `ApprovalStep.restricted_to_channel`'s docstring.
    # Exposed on every read so a frontend can hide/disable a "Decide"
    # action it could never actually submit successfully.
    restricted_to_channel: str | None
    # Approval Workflow Changes v2 — only meaningful when both
    # `approver_employee_id` and `approver_permission_code` are set
    # (dual-mode). Names the one channel on which `approver_permission_code`
    # governs instead of `approver_employee_id` — see
    # `ApprovalStep.permission_required_for_channel`'s docstring. A frontend
    # replicates the same "which check applies on MY channel" logic this
    # engine enforces server-side, to hide a "Decide" action it could never
    # actually submit successfully.
    permission_required_for_channel: str | None
    # Approval Workflow Changes v2 — who actually clicked Approve/Reject,
    # distinct from `approver_employee_id` (who was originally assigned/
    # referenced). `None` until decided. See
    # `ApprovalStep.decided_by_employee_id`'s docstring.
    decided_by_employee_id: uuid.UUID | None
    # Enrichment, resolved by `ApprovalService` via `EmployeeLookupPort`
    # (never by this DTO or the mapper) — populated for `decided_by_
    # employee_id` once decided, else `approver_employee_id` while pending;
    # always `None` for a still-pending permission-based (non-dual-mode)
    # step, since there is no single employee to name yet. Lets the HR
    # system show "Pending — Jane Doe (EMP-0042)" / "Approved by ..." without
    # this engine ever knowing the approver is "a manager."
    approver_employee_name: str | None
    approver_employee_code: str | None
    status: str
    comments: str | None
    decided_at: datetime | None


@dataclass(frozen=True)
class ApprovalRequestResponse:
    id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    requested_by_employee_id: uuid.UUID
    subject_summary: str
    status: str
    current_level: int
    steps: list[ApprovalStepResponse] = field(default_factory=list)
