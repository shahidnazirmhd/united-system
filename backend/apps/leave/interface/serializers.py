"""DRF serializers for Leave.

Pure protocol translation (JSON <-> application-layer DTOs), no business
validation — matching Employees'/Identity's `interface/serializers.py`
convention exactly (date-range/balance/overlap rules all live in
`LeaveValidationService`, never here).
"""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.leave.domain.enums import LeaveBalanceAdjustmentType, LeaveRequestStatus


class LeaveTypeResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField()
    default_annual_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    is_paid = serializers.BooleanField()
    requires_approval = serializers.BooleanField()
    is_active = serializers.BooleanField()
    maps_to_employee_status = serializers.ChoiceField(
        choices=["sick_leave", "annual_leave"], allow_null=True, required=False
    )


class LeaveBalanceResponseSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    leave_type_id = serializers.UUIDField()
    leave_type_name = serializers.CharField(allow_null=True)
    year = serializers.IntegerField()
    entitled_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    used_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    carried_forward_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    available_days = serializers.DecimalField(max_digits=6, decimal_places=2)
    pending_days = serializers.DecimalField(max_digits=6, decimal_places=2)


class LeaveRequestResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    employee_id = serializers.UUIDField()
    leave_type_id = serializers.UUIDField()
    leave_type_name = serializers.CharField(allow_null=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    total_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    working_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    reason = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=LeaveRequestStatus.values())
    approved_by = serializers.UUIDField(allow_null=True)
    decided_at = serializers.DateTimeField(allow_null=True)
    decision_comments = serializers.CharField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    cancellation_reason = serializers.CharField(allow_null=True)
    balance_at_application = serializers.DecimalField(
        max_digits=6, decimal_places=2, allow_null=True
    )
    # Populated only on the HR-wide "manage" list (Phase 13 review
    # requirement) — null on every other read (self-service/single-employee
    # history already have employee context from the caller).
    employee_name = serializers.CharField(allow_null=True)
    employee_code = serializers.CharField(allow_null=True)
    # --- HR Leave Workflow round (skip-level-1 + initiator tracking) -----
    level1_skipped = serializers.BooleanField()
    level1_skip_reason = serializers.CharField(allow_null=True)
    initiated_via = serializers.ChoiceField(choices=["hr", "telegram"], allow_null=True)
    initiator_user_id = serializers.UUIDField(allow_null=True)
    initiator_telegram_user_id = serializers.IntegerField(allow_null=True)
    initiator_display_name = serializers.CharField(allow_null=True)


class Level1ApprovalCheckResponseSerializer(serializers.Serializer):
    """HR Leave Workflow round, item 1 — response shape for the pre-submit
    confirmation-dialog preview endpoint."""

    will_skip_level1 = serializers.BooleanField()
    skip_reason = serializers.CharField(allow_null=True)


class ApplyLeaveSerializer(serializers.Serializer):
    leave_type_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class CancelLeaveSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class YearQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(required=False, allow_null=True, default=None)


# --- Leave Type Management (Phase 13, leave.manage_leave) ---------------


class CreateLeaveTypeSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    code = serializers.CharField(max_length=20)
    default_annual_days = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    is_paid = serializers.BooleanField(default=True)
    requires_approval = serializers.BooleanField(default=True)
    maps_to_employee_status = serializers.ChoiceField(
        choices=["sick_leave", "annual_leave"], allow_null=True, required=False, default=None
    )


class UpdateLeaveTypeSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    code = serializers.CharField(max_length=20)
    default_annual_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    is_paid = serializers.BooleanField()
    requires_approval = serializers.BooleanField()
    is_active = serializers.BooleanField(default=True)
    maps_to_employee_status = serializers.ChoiceField(
        choices=["sick_leave", "annual_leave"], allow_null=True, required=False, default=None
    )


class LeaveTypeListQuerySerializer(serializers.Serializer):
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
    search = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=25)


# --- Leave Balance Adjustment / Opening (Phase 13, leave.manage_leave) ---


class AdjustLeaveBalanceSerializer(serializers.Serializer):
    employee_id = serializers.UUIDField()
    leave_type_id = serializers.UUIDField()
    year = serializers.IntegerField()
    entitled_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    used_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    carried_forward_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    reason = serializers.CharField()


class LeaveBalanceAdjustmentResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    employee_id = serializers.UUIDField()
    leave_type_id = serializers.UUIDField()
    year = serializers.IntegerField()
    adjustment_type = serializers.ChoiceField(choices=LeaveBalanceAdjustmentType.values())
    previous_entitled_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    previous_used_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    previous_carried_forward_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    new_entitled_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    new_used_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    new_carried_forward_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    reason = serializers.CharField()
    adjusted_by = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()


class LeaveHistoryQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LeaveRequestStatus.values(), required=False, allow_null=True, default=None)
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=25)


class ManageLeaveRequestsQuerySerializer(serializers.Serializer):
    """Query params for the HR-wide "manage" leave request list (Phase 13
    review requirement) — every filter is optional; an HR/Admin browsing
    the whole queue supplies as many or as few as they need."""

    employee_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    status = serializers.ChoiceField(choices=LeaveRequestStatus.values(), required=False, allow_null=True, default=None)
    leave_type_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    start_date_from = serializers.DateField(required=False, allow_null=True, default=None)
    start_date_to = serializers.DateField(required=False, allow_null=True, default=None)
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=25)


# --- Telegram Gateway-facing (mirrors apps.employees.interface.serializers
# TelegramUserIdQuerySerializer, kept as this module's own copy rather than
# importing Employees' — interface-layer serializers are per-module by
# convention throughout this codebase, avoiding a needless interface-layer
# cross-module dependency for a one-field shape). ------------------------


class TelegramUserIdQuerySerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()


class TelegramLeaveBalanceQuerySerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()
    year = serializers.IntegerField(required=False, allow_null=True, default=None)


class TelegramLeaveHistoryQuerySerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=LeaveRequestStatus.values(), required=False, allow_null=True, default=None)
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=25)


class ApplyLeaveTelegramSerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()
    leave_type_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class CancelLeaveTelegramSerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()
    cancellation_reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
