"""DRF serializers for Leave.

Pure protocol translation (JSON <-> application-layer DTOs), no business
validation — matching Employees'/Identity's `interface/serializers.py`
convention exactly (date-range/balance/overlap rules all live in
`LeaveValidationService`, never here).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.leave.domain.enums import LeaveRequestStatus


class LeaveTypeResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField()
    default_annual_days = serializers.DecimalField(max_digits=5, decimal_places=2)
    is_paid = serializers.BooleanField()
    requires_approval = serializers.BooleanField()
    is_active = serializers.BooleanField()


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
    reason = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=LeaveRequestStatus.values())
    approved_by = serializers.UUIDField(allow_null=True)
    decided_at = serializers.DateTimeField(allow_null=True)
    decision_comments = serializers.CharField(allow_null=True)
    cancelled_at = serializers.DateTimeField(allow_null=True)
    cancellation_reason = serializers.CharField(allow_null=True)


class ApplyLeaveSerializer(serializers.Serializer):
    leave_type_id = serializers.UUIDField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class CancelLeaveSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class YearQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(required=False, allow_null=True, default=None)


class LeaveHistoryQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=LeaveRequestStatus.values(), required=False, allow_null=True, default=None)
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
