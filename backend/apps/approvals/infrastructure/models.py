"""Django ORM models for the generic Approval Engine.

`ApprovalStepRecord.approval_request` IS a real ForeignKey — both tables
belong to this same module/aggregate (matching
`apps.leave.infrastructure.models.LeaveBalanceRecord.leave_type`'s
identical "same-module real FK" precedent). Every other cross-module id on
either model (`subject_id`, `requested_by_employee_id`,
`approver_employee_id`) is a plain UUID field, never a ForeignKey, per
HRMS_Database_Design.md section 5 (no cross-module foreign keys) — same
discipline every other module's infrastructure layer already follows.
"""
from __future__ import annotations

from django.db import models

from apps.approvals.domain.enums import ApprovalChannel, ApprovalStatus, ApprovalStepStatus
from shared_kernel.infrastructure.base_models import BaseModel


class ApprovalRequestRecord(BaseModel):
    # Opaque to this module — see domain/entities.py's docstring.
    subject_type = models.CharField(max_length=100)
    subject_id = models.UUIDField()
    # Logical reference to employees_employees.id — plain UUID, never a
    # ForeignKey (cross-module reference).
    requested_by_employee_id = models.UUIDField()
    subject_summary = models.TextField()
    status = models.CharField(
        max_length=20, choices=ApprovalStatus.choices(), default=ApprovalStatus.PENDING.value
    )
    current_level = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "approval_requests"
        indexes = [
            # The exact shape get_pending_by_subject/list_by_subject query
            # by — see infrastructure/repositories.py.
            models.Index(fields=["subject_type", "subject_id"], name="approval_requests_subject_idx"),
            models.Index(fields=["requested_by_employee_id"], name="approval_req_requester_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(current_level__gte=1), name="approval_requests_level_gte_1"),
        ]

    def __str__(self) -> str:
        return f"approval-request {self.subject_type}:{self.subject_id} ({self.status})"


class ApprovalStepRecord(BaseModel):
    approval_request = models.ForeignKey(
        ApprovalRequestRecord, on_delete=models.CASCADE, related_name="steps"
    )
    level = models.PositiveSmallIntegerField()
    # Logical reference to employees_employees.id — plain UUID, never a
    # ForeignKey (cross-module reference). Nullable: exactly one of this
    # field and `approver_permission_code` below is set (see
    # apps.approvals.domain.value_objects.ApproverAssignment) — null here
    # specifically means "assigned by permission instead," never
    # "unassigned."
    approver_employee_id = models.UUIDField(null=True, blank=True)
    # A permission code (e.g. "leave.manage_leave") any employee currently
    # holding it may decide this step — added so a subject module can
    # assign a level to a whole permission cohort instead of one named
    # employee (see ApproverAssignment.for_permission's docstring).
    approver_permission_code = models.CharField(max_length=100, null=True, blank=True)
    # Approval Workflow Changes review round: which channel
    # (`ApprovalChannel.WEB`/`.TELEGRAM`) this step may be decided from, or
    # `None` for "either, no restriction" — the only behavior that existed
    # before this field. Copied verbatim from
    # `ApproverAssignment.restricted_to_channel` at step-creation time; see
    # that value object's docstring for the full reasoning. This module
    # never branches on the value beyond an equality check
    # (`ApprovalStep.is_decidable_via_channel`).
    restricted_to_channel = models.CharField(
        max_length=20, null=True, blank=True, choices=ApprovalChannel.choices()
    )
    # Approval Workflow Changes v2: only meaningful when both
    # `approver_employee_id` and `approver_permission_code` are set
    # (dual-mode) — see `apps.approvals.domain.entities.ApprovalStep
    # .permission_required_for_channel`'s docstring.
    permission_required_for_channel = models.CharField(
        max_length=20, null=True, blank=True, choices=ApprovalChannel.choices()
    )
    # Approval Workflow Changes v2: who actually decided this step, distinct
    # from `approver_employee_id` (who was originally assigned/referenced).
    # Plain UUID, never a ForeignKey (cross-module reference, same
    # discipline as `approver_employee_id`). `None` until decided.
    decided_by_employee_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=ApprovalStepStatus.choices(), default=ApprovalStepStatus.PENDING.value
    )
    comments = models.TextField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "approval_steps"
        constraints = [
            models.UniqueConstraint(
                fields=["approval_request", "level"], name="approval_steps_unique_request_level"
            ),
            # Approval Workflow Changes v2: relaxed from "exactly one" to
            # "at least one" — a dual-mode step (see `ApproverAssignment
            # .for_employee_or_permission_by_channel`) deliberately sets
            # BOTH `approver_employee_id` and `approver_permission_code`,
            # e.g. Leave's level 1 (manager via Telegram,
            # `approvals.level1_approve` via the web). A step with neither
            # set is still never valid — that would be "assigned to no
            # one," which this engine has never supported.
            models.CheckConstraint(
                check=~models.Q(approver_employee_id__isnull=True, approver_permission_code__isnull=True),
                name="approval_steps_at_least_one_approver_mode",
            ),
            # `permission_required_for_channel` only makes sense when BOTH
            # approver fields are populated — see the field's docstring.
            # Mirrors `ApproverAssignment.__post_init__`'s identical
            # application-layer guard, enforced again here at the DB level
            # since this table can in principle be written to outside this
            # process too.
            models.CheckConstraint(
                check=(
                    models.Q(permission_required_for_channel__isnull=True)
                    | (
                        models.Q(approver_employee_id__isnull=False)
                        & models.Q(approver_permission_code__isnull=False)
                    )
                ),
                name="approval_steps_channel_permission_requires_dual_mode",
            ),
        ]
        indexes = [
            # The exact shape list_pending_for_approver queries by.
            models.Index(fields=["approver_employee_id", "status"], name="approval_steps_appr_stat_idx"),
            models.Index(fields=["approver_permission_code", "status"], name="approval_steps_perm_stat_idx"),
        ]

    def __str__(self) -> str:
        approver = self.approver_employee_id or f"permission:{self.approver_permission_code}"
        return f"approval-step request:{self.approval_request_id} level:{self.level} ({self.status}) approver:{approver}"
