"""Django ORM-backed implementations of the Approval Engine's repository
interfaces. Follows `apps.leave.infrastructure.repositories`'s exact shape:
extends shared_kernel's generic `DjangoBaseRepository` for CRUD/pagination,
adding only the entity-specific lookups the generic base can't express.
"""
from __future__ import annotations

import uuid

from apps.approvals.domain.entities import ApprovalRequest, ApprovalStep
from apps.approvals.domain.enums import ApprovalStatus, ApprovalStepStatus
from apps.approvals.domain.repositories import ApprovalRequestRepository, ApprovalStepRepository
from apps.approvals.infrastructure.models import ApprovalRequestRecord, ApprovalStepRecord
from shared_kernel.infrastructure.base_repository import DjangoBaseRepository


def _approval_request_to_domain(record: ApprovalRequestRecord) -> ApprovalRequest:
    return ApprovalRequest(
        id=record.id,
        subject_type=record.subject_type,
        subject_id=record.subject_id,
        requested_by_employee_id=record.requested_by_employee_id,
        subject_summary=record.subject_summary,
        status=ApprovalStatus(record.status),
        current_level=record.current_level,
    )


def _approval_step_to_domain(record: ApprovalStepRecord) -> ApprovalStep:
    return ApprovalStep(
        id=record.id,
        approval_request_id=record.approval_request_id,
        level=record.level,
        approver_employee_id=record.approver_employee_id,
        approver_permission_code=record.approver_permission_code,
        restricted_to_channel=record.restricted_to_channel,
        permission_required_for_channel=record.permission_required_for_channel,
        decided_by_employee_id=record.decided_by_employee_id,
        status=ApprovalStepStatus(record.status),
        comments=record.comments,
        decided_at=record.decided_at,
    )


class DjangoApprovalRequestRepository(
    DjangoBaseRepository[ApprovalRequestRecord, ApprovalRequest], ApprovalRequestRepository
):
    model = ApprovalRequestRecord

    def _to_entity(self, record: ApprovalRequestRecord) -> ApprovalRequest:
        return _approval_request_to_domain(record)

    def _to_record_kwargs(self, entity: ApprovalRequest) -> dict[str, object]:
        return {
            "subject_type": entity.subject_type,
            "subject_id": entity.subject_id,
            "requested_by_employee_id": entity.requested_by_employee_id,
            "subject_summary": entity.subject_summary,
            "status": entity.status.value,
            "current_level": entity.current_level,
        }

    def get_pending_by_subject(self, *, subject_type: str, subject_id: uuid.UUID) -> ApprovalRequest | None:
        record = (
            self._base_queryset()
            .filter(subject_type=subject_type, subject_id=subject_id, status=ApprovalStatus.PENDING.value)
            .first()
        )
        return self._to_entity(record) if record is not None else None

    def list_by_subject(self, *, subject_type: str, subject_id: uuid.UUID) -> list[ApprovalRequest]:
        records = self._base_queryset().filter(subject_type=subject_type, subject_id=subject_id).order_by("created_at")
        return [self._to_entity(r) for r in records]


class DjangoApprovalStepRepository(DjangoBaseRepository[ApprovalStepRecord, ApprovalStep], ApprovalStepRepository):
    model = ApprovalStepRecord

    def _to_entity(self, record: ApprovalStepRecord) -> ApprovalStep:
        return _approval_step_to_domain(record)

    def _to_record_kwargs(self, entity: ApprovalStep) -> dict[str, object]:
        return {
            "approval_request_id": entity.approval_request_id,
            "level": entity.level,
            "approver_employee_id": entity.approver_employee_id,
            "approver_permission_code": entity.approver_permission_code,
            "restricted_to_channel": entity.restricted_to_channel,
            "permission_required_for_channel": entity.permission_required_for_channel,
            "decided_by_employee_id": entity.decided_by_employee_id,
            "status": entity.status.value,
            "comments": entity.comments,
            "decided_at": entity.decided_at,
        }

    def get_by_request_and_level(self, *, approval_request_id: uuid.UUID, level: int) -> ApprovalStep | None:
        record = self._base_queryset().filter(approval_request_id=approval_request_id, level=level).first()
        return self._to_entity(record) if record is not None else None

    def list_by_request(self, *, approval_request_id: uuid.UUID) -> list[ApprovalStep]:
        records = self._base_queryset().filter(approval_request_id=approval_request_id).order_by("level")
        return [self._to_entity(r) for r in records]

    def list_pending_for_approver(
        self, *, approver_employee_id: uuid.UUID, held_permission_codes: frozenset[str]
    ) -> list[ApprovalStep]:
        from django.db.models import Q

        condition = Q(approver_employee_id=approver_employee_id)
        if held_permission_codes:
            condition |= Q(approver_permission_code__in=held_permission_codes)
        records = (
            self._base_queryset()
            .filter(condition, status=ApprovalStepStatus.PENDING.value)
            .order_by("created_at")
        )
        return [self._to_entity(r) for r in records]
