"""Entity <-> response-DTO translation for Leave.

Kept as free functions in their own module rather than methods on the
entities themselves, matching `apps.employees.application.mappers`'
precedent exactly (domain entities stay framework/DTO-agnostic; only this
file knows both shapes).
"""
from __future__ import annotations

from decimal import Decimal

from apps.leave.application.dtos import LeaveBalanceResponse, LeaveRequestResponse, LeaveTypeResponse
from apps.leave.domain.entities import LeaveBalance, LeaveRequest, LeaveType


def leave_type_to_response(leave_type: LeaveType) -> LeaveTypeResponse:
    return LeaveTypeResponse(
        id=leave_type.id,
        name=leave_type.name,
        code=leave_type.code,
        default_annual_days=leave_type.default_annual_days,
        is_paid=leave_type.is_paid,
        requires_approval=leave_type.requires_approval,
        is_active=leave_type.is_active,
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


def leave_request_to_response(request: LeaveRequest, *, leave_type_name: str | None = None) -> LeaveRequestResponse:
    return LeaveRequestResponse(
        id=request.id,
        employee_id=request.employee_id,
        leave_type_id=request.leave_type_id,
        leave_type_name=leave_type_name,
        start_date=request.date_range.start_date,
        end_date=request.date_range.end_date,
        total_days=request.total_days,
        reason=request.reason,
        status=request.status.value,
        approved_by=request.approved_by,
        decided_at=request.decided_at,
        decision_comments=request.decision_comments,
        cancelled_at=request.cancelled_at,
        cancellation_reason=request.cancellation_reason,
    )
