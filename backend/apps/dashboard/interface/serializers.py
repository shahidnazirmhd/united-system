"""DRF serializers for Dashboard. Pure protocol translation, no business
validation — matching every other module's `interface/serializers.py`."""
from __future__ import annotations

from rest_framework import serializers


class EmployeeDepartmentStatSerializer(serializers.Serializer):
    department_id = serializers.UUIDField()
    department_name = serializers.CharField()
    count = serializers.IntegerField()


class EmployeeStatisticsResponseSerializer(serializers.Serializer):
    total_employees = serializers.IntegerField()
    active_count = serializers.IntegerField()
    inactive_count = serializers.IntegerField()
    terminated_count = serializers.IntegerField()
    status_breakdown = serializers.DictField(child=serializers.IntegerField())
    current_status_breakdown = serializers.DictField(child=serializers.IntegerField())
    employment_type_breakdown = serializers.DictField(child=serializers.IntegerField())
    department_breakdown = EmployeeDepartmentStatSerializer(many=True)
    new_hires_this_month = serializers.IntegerField()


class LeaveTypeStatSerializer(serializers.Serializer):
    leave_type_id = serializers.UUIDField()
    leave_type_name = serializers.CharField()
    count = serializers.IntegerField()


class LeaveMonthlyStatSerializer(serializers.Serializer):
    month = serializers.CharField()
    count = serializers.IntegerField()


class LeaveStatisticsResponseSerializer(serializers.Serializer):
    status_breakdown = serializers.DictField(child=serializers.IntegerField())
    leave_type_breakdown = LeaveTypeStatSerializer(many=True)
    monthly_trend = LeaveMonthlyStatSerializer(many=True)
    on_leave_today_count = serializers.IntegerField()


class RecentActivityItemSerializer(serializers.Serializer):
    leave_request_id = serializers.UUIDField()
    employee_id = serializers.UUIDField()
    employee_name = serializers.CharField(allow_null=True)
    employee_code = serializers.CharField(allow_null=True)
    leave_type_name = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    updated_at = serializers.DateTimeField(allow_null=True)


class UpcomingHolidaySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    holiday_date = serializers.DateField()
    description = serializers.CharField()
