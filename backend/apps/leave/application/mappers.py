"""Entity <-> response-DTO translation for Leave.

Kept as free functions in their own module rather than methods on the
entities themselves, matching `apps.employees.application.mappers`'
precedent exactly (domain entities stay framework/DTO-agnostic; only this
file knows both shapes).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from apps.leave.application.dtos import (
    LeaveBalanceAdjustmentResponse,
    LeaveBalanceResponse,
    LeaveRequestResponse,
    LeaveTypeResponse,
)
from apps.leave.domain.entities import LeaveBalance, LeaveBalanceAdjustment, LeaveRequest, LeaveType


def leave_type_to_response(leave_type: LeaveType) -> LeaveTypeResponse:
    return LeaveTypeResponse(
        id=leave_type.id,
        name=leave_type.name,
        code=leave_type.code,
        default_annual_days=leave_type.default_annual_days,
        is_paid=leave_type.is_paid,
        requires_approval=leave_type.requires_approval,
        is_active=leave_type.is_active,
        maps_to_employee_status=leave_type.maps_to_employee_status,
    )


def leave_balance_to_response(
    balance: LeaveBalance, *, leave_type_name: str | None = None, pending_days: Decimal = Decimal("0")
) -> LeaveBalanceResponse:
    return LeaveBalanceResponse(
        employee_id=balance.employee_id,
        leave_type_id=balance.leave_type_id,
        leave_type_name=leave_type_name,
        year=balance.year,
        entitled_days=balance.entitled_days,
        used_days=balance.used_days,
        carried_forward_days=balance.carried_forward_days,
        available_days=balance.available_days,
        pending_days=pending_days,
    )


def leave_request_to_response(
    request: LeaveRequest,
    *,
    leave_type_name: str | None = None,
    employee_name: str | None = None,
    employee_code: str | None = None,
) -> LeaveRequestResponse:
    return LeaveRequestResponse(
        id=request.id,
        employee_id=request.employee_id,
        leave_type_id=request.leave_type_id,
        leave_type_name=leave_type_name,
        start_date=request.date_range.start_date,
        end_date=request.date_range.end_date,
        total_days=request.total_days,
        working_days=request.working_days,
        reason=request.reason,
        status=request.status.value,
        approved_by=request.approved_by,
        decided_at=request.decided_at,
        decision_comments=request.decision_comments,
        cancelled_at=request.cancelled_at,
        cancellation_reason=request.cancellation_reason,
        balance_at_application=request.balance_at_application,
        employee_name=employee_name,
        employee_code=employee_code,
        updated_at=request.updated_at,
    )


def leave_balance_adjustment_to_response(
    adjustment: LeaveBalanceAdjustment, *, adjusted_by: uuid.UUID | None, created_at: datetime
) -> LeaveBalanceAdjustmentResponse:
    """`adjusted_by`/`created_at` are passed in rather than read off
    `adjustment` — `LeaveBalanceAdjustment` (domain/entities.py) has
    neither field, on purpose (see that entity's docstring): "who/when" is
    a persistence-layer audit concern, and the caller
    (`LeaveBalanceService.adjust_balance`) already has both values in hand
    without needing to read them back from the database."""
    return LeaveBalanceAdjustmentResponse(
        id=adjustment.id,
        employee_id=adjustment.employee_id,
        leave_type_id=adjustment.leave_type_id,
        year=adjustment.year,
        adjustment_type=adjustment.adjustment_type.value,
        previous_entitled_days=adjustment.previous_entitled_days,
        previous_used_days=adjustment.previous_used_days,
        previous_carried_forward_days=adjustment.previous_carried_forward_days,
        new_entitled_days=adjustment.new_entitled_days,
        new_used_days=adjustment.new_used_days,
        new_carried_forward_days=adjustment.new_carried_forward_days,
        reason=adjustment.reason,
        adjusted_by=adjusted_by,
        created_at=created_at,
    )
