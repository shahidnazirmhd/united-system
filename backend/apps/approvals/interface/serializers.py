"""DRF serializers for the Approval Engine.

Pure protocol translation (JSON <-> application-layer DTOs), no business
validation — matching every other module's `interface/serializers.py`
convention exactly (every real rule lives in `ApprovalService`/domain
entities, never here).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.approvals.application.services.approval_service import DECISION_APPROVE, DECISION_REJECT

_DECISION_CHOICES = [DECISION_APPROVE, DECISION_REJECT]


class ApprovalStepResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    approval_request_id = serializers.UUIDField()
    level = serializers.IntegerField()
    # At least one of these two is ever non-null; a dual-mode step (Approval
    # Workflow Changes v2 — see apps.approvals.domain.value_objects
    # .ApproverAssignment.for_employee_or_permission_by_channel) sets BOTH.
    approver_employee_id = serializers.UUIDField(allow_null=True)
    approver_permission_code = serializers.CharField(allow_null=True)
    # Approval Workflow Changes review round — see
    # apps.approvals.domain.entities.ApprovalStep.restricted_to_channel.
    restricted_to_channel = serializers.CharField(allow_null=True)
    # Approval Workflow Changes v2 — see
    # apps.approvals.domain.entities.ApprovalStep
    # .permission_required_for_channel.
    permission_required_for_channel = serializers.CharField(allow_null=True)
    # Approval Workflow Changes v2 — who actually decided this step; see
    # apps.approvals.domain.entities.ApprovalStep.decided_by_employee_id.
    decided_by_employee_id = serializers.UUIDField(allow_null=True)
    approver_employee_name = serializers.CharField(allow_null=True)
    approver_employee_code = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    comments = serializers.CharField(allow_null=True)
    decided_at = serializers.DateTimeField(allow_null=True)


class ApprovalRequestResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    subject_type = serializers.CharField()
    subject_id = serializers.UUIDField()
    requested_by_employee_id = serializers.UUIDField()
    subject_summary = serializers.CharField()
    status = serializers.CharField()
    current_level = serializers.IntegerField()
    steps = ApprovalStepResponseSerializer(many=True)


class DecideApprovalSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=_DECISION_CHOICES)
    comments = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


# --- Telegram Gateway-facing (own copy, matching apps.leave.interface.
# serializers's precedent of not importing another module's interface-layer
# serializer for a one-field shape). ---------------------------------------


class TelegramUserIdQuerySerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()


class DecideApprovalTelegramSerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()
    approval_request_id = serializers.UUIDField()
    decision = serializers.ChoiceField(choices=_DECISION_CHOICES)
    comments = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
