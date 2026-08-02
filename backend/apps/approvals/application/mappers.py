"""Entity <-> response-DTO translation for the Approval Engine.

Kept as free functions in their own module, matching
`apps.leave.application.mappers`'s precedent exactly (domain entities stay
framework/DTO-agnostic; only this file knows both shapes).
"""
from __future__ import annotations

from apps.approvals.application.dtos import ApprovalRequestResponse, ApprovalStepResponse
from apps.approvals.domain.entities import ApprovalRequest, ApprovalStep


def approval_step_to_response(step: ApprovalStep) -> ApprovalStepResponse:
    return ApprovalStepResponse(
        id=step.id,
        approval_request_id=step.approval_request_id,
        level=step.level,
        approver_employee_id=step.approver_employee_id,
        approver_permission_code=step.approver_permission_code,
        restricted_to_channel=step.restricted_to_channel,
        permission_required_for_channel=step.permission_required_for_channel,
        decided_by_employee_id=step.decided_by_employee_id,
        # Never resolved here — this mapper stays a pure entity<->DTO
        # translation with no port dependency. `ApprovalService` fills
        # these in afterward (see its `_enrich_step` helper), preferring
        # `decided_by_employee_id` once decided, else `approver_employee_id`
        # while pending.
        approver_employee_name=None,
        approver_employee_code=None,
        status=step.status.value,
        comments=step.comments,
        decided_at=step.decided_at,
    )


def approval_request_to_response(
    request: ApprovalRequest, *, steps: list[ApprovalStep] | None = None
) -> ApprovalRequestResponse:
    return ApprovalRequestResponse(
        id=request.id,
        subject_type=request.subject_type,
        subject_id=request.subject_id,
        requested_by_employee_id=request.requested_by_employee_id,
        subject_summary=request.subject_summary,
        status=request.status.value,
        current_level=request.current_level,
        steps=[approval_step_to_response(s) for s in steps] if steps is not None else [],
    )
