"""Input/output DTOs for Leave application services.

Interface-layer serializers convert HTTP request/response JSON to/from
these — services never see a DRF Request/Response object, matching
Employees'/Identity's `application/dtos.py` convention exactly.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True)
class ApplyLeaveRequest:
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str | None = None
    created_by: uuid.UUID | None = None


@dataclass(frozen=True)
class CancelLeaveRequest:
    leave_request_id: uuid.UUID
    # The employee_id the *caller* resolves to — used to enforce that a
    # self-service caller can only cancel their own request (see
    # domain/exceptions.py LeaveRequestOwnershipError). An HR admin caller
    # passes None here to bypass the ownership check, matching how
    # `employees.manage_employees` already grants broader-than-self access
    # elsewhere in this codebase.
    acting_employee_id: uuid.UUID | None
    cancellation_reason: str | None = None
    cancelled_by: uuid.UUID | None = None


@dataclass(frozen=True)
class ApproveLeaveRequest:
    """Approval module extension point — constructed and unit-tested this
    phase, not reachable through any REST endpoint yet."""

    leave_request_id: uuid.UUID
    approved_by: uuid.UUID
    comments: str | None = None


@dataclass(frozen=True)
class RejectLeaveRequest:
    leave_request_id: uuid.UUID
    comments: str | None = None


@dataclass(frozen=True)
class LeaveRequestResponse:
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_type_name: str | None
    start_date: date
    end_date: date
    total_days: Decimal
    reason: str | None
    status: str
    approved_by: uuid.UUID | None
    decided_at: datetime | None
    decision_comments: str | None
    cancelled_at: datetime | None
    cancellation_reason: str | None


@dataclass(frozen=True)
class LeaveBalanceResponse:
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    leave_type_name: str | None
    year: int
    entitled_days: Decimal
    used_days: Decimal
    carried_forward_days: Decimal
    available_days: Decimal
    pending_days: Decimal


@dataclass(frozen=True)
class LeaveTypeResponse:
    id: uuid.UUID
    name: str
    code: str
    default_annual_days: Decimal
    is_paid: bool
    requires_approval: bool
    is_active: bool


@dataclass(frozen=True)
class LeaveHistoryQuery:
    employee_id: uuid.UUID
    status: str | None = None
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 25
