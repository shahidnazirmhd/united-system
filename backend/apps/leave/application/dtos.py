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
    # Round 14 item 6 — working days (excludes the configured week-off day
    # and holidays), the value balance is actually deducted against.
    working_days: Decimal
    reason: str | None
    status: str
    approved_by: uuid.UUID | None
    decided_at: datetime | None
    decision_comments: str | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    # Round 14 item 2 — snapshot of available balance at apply time. None
    # only for legacy rows created before this column existed.
    balance_at_application: Decimal | None = None
    # Populated only by the HR-wide "manage" list (Phase 13 review
    # requirement) — every other read already has employee context from the
    # caller (self-service: the caller *is* the employee; single-employee
    # history: the caller already picked one), so left `None` everywhere
    # else rather than adding an extra lookup no other caller needs.
    employee_name: str | None = None
    employee_code: str | None = None
    # Phase 14 (Dashboard) — see `LeaveRequest.updated_at`'s docstring for
    # why ordering by this column (via `LeaveService.list_all_requests_admin`)
    # is what backs the Dashboard's "recent leave activity" feed.
    updated_at: datetime | None = None


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
    maps_to_employee_status: str | None = None


@dataclass(frozen=True)
class LeaveHistoryQuery:
    employee_id: uuid.UUID
    status: str | None = None
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 25


# --- Leave Type Management (Phase 13) ---------------------------------


@dataclass(frozen=True)
class CreateLeaveTypeRequest:
    name: str
    code: str
    default_annual_days: Decimal = Decimal("0")
    is_paid: bool = True
    requires_approval: bool = True
    # Round 14 items 6/8 — see domain/employee_status_mapping.py for the
    # allowed values ("sick_leave"/"annual_leave") and why this is a plain
    # string, not an imported Employees enum. None (the default) means this
    # leave type never changes the employee's Current Status.
    maps_to_employee_status: str | None = None
    created_by: uuid.UUID | None = None


@dataclass(frozen=True)
class UpdateLeaveTypeRequest:
    leave_type_id: uuid.UUID
    name: str
    code: str
    default_annual_days: Decimal
    is_paid: bool
    requires_approval: bool
    is_active: bool = True
    maps_to_employee_status: str | None = None
    updated_by: uuid.UUID | None = None


@dataclass(frozen=True)
class LeaveTypeListQuery:
    """Admin listing (Manage Leave Types) — unlike `list_leave_types()`
    (always active-only, used by every apply-leave dropdown), this includes
    inactive rows so HR can find and reactivate one."""

    is_active: bool | None = None
    search: str | None = None
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 25


# --- Leave Balance Adjustment / Opening (Phase 13) --------------------


@dataclass(frozen=True)
class AdjustLeaveBalanceRequest:
    """One upsert path for both named Phase 13 features: creates the
    balance row (recorded as `adjustment_type="opening"`) if none exists
    yet for this employee/leave type/year, or overwrites the existing row's
    absolute values (recorded as `"adjustment"`) otherwise — see
    `LeaveBalanceService.adjust_balance`'s docstring for why one write path
    is enough for both UI entry points."""

    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int
    entitled_days: Decimal
    used_days: Decimal
    carried_forward_days: Decimal
    reason: str
    adjusted_by: uuid.UUID | None = None


@dataclass(frozen=True)
class LeaveBalanceAdjustmentResponse:
    id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int
    adjustment_type: str
    previous_entitled_days: Decimal
    previous_used_days: Decimal
    previous_carried_forward_days: Decimal
    new_entitled_days: Decimal
    new_used_days: Decimal
    new_carried_forward_days: Decimal
    reason: str
    adjusted_by: uuid.UUID | None
    created_at: datetime


# --- Statistics (Phase 14: Dashboard) ----------------------------------


@dataclass(frozen=True)
class LeaveTypeStat:
    leave_type_id: uuid.UUID
    leave_type_name: str
    count: int


@dataclass(frozen=True)
class LeaveMonthlyStat:
    month: str  # "YYYY-MM"
    count: int


@dataclass(frozen=True)
class LeaveStatisticsResponse:
    """Aggregate counts computed against this module's own data, exposed as
    a public read so `apps.dashboard` can consume it through a reverse
    port (`LeaveStatisticsPort`) exactly like every other cross-module read
    in this codebase — see `LeaveRequestService.get_statistics`.

    `status_breakdown` is all-time (every request ever, regardless of when),
    matching the KPI-card convention every other "how many X" figure in this
    codebase already uses (e.g. `EmployeeStatisticsResponse.status_breakdown`).
    `monthly_trend` covers the trailing window `LeaveRequestService
    .get_statistics` requests (default 6 months) and is backfilled with
    zero-count months so a line/area chart never shows a gap.
    """

    status_breakdown: dict[str, int]
    leave_type_breakdown: list[LeaveTypeStat]
    monthly_trend: list[LeaveMonthlyStat]
    on_leave_today_count: int
