"""Dashboard's own output DTOs.

These deliberately mirror the shape of `EmployeeStatisticsResponse` /
`LeaveStatisticsResponse` (etc.) that Employees/Leave/Attendance already
expose on their own `application/dtos.py`, but they are NOT the same
classes imported across a module boundary — each source module's own DTO
is that module's public contract for ITS OWN interface layer (its own
views/serializers), not a shape Dashboard should reach into and reuse
directly. Dashboard defines its own copies here so that a future change to,
say, `LeaveStatisticsResponse` (driven entirely by Leave's own needs) can
never silently break Dashboard's contract, and vice versa — the translation
happens explicitly in `infrastructure/*_adapter.py`, one field at a time.
This is the same reasoning `apps.leave.application.ports.HolidayLookupPort`
already established for its own `LeaveHoliday`-shaped read, applied here to
three source modules instead of one.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime


# --- Employee Statistics (source: apps.employees) -----------------------


@dataclass(frozen=True)
class EmployeeDepartmentStat:
    department_id: uuid.UUID
    department_name: str
    count: int


@dataclass(frozen=True)
class EmployeeStatisticsResponse:
    total_employees: int
    active_count: int
    inactive_count: int
    terminated_count: int
    status_breakdown: dict[str, int]
    current_status_breakdown: dict[str, int]
    employment_type_breakdown: dict[str, int]
    department_breakdown: list[EmployeeDepartmentStat]
    new_hires_this_month: int


# --- Leave Statistics (source: apps.leave) -------------------------------


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
    status_breakdown: dict[str, int]
    leave_type_breakdown: list[LeaveTypeStat]
    monthly_trend: list[LeaveMonthlyStat]
    on_leave_today_count: int


# --- Recent Activity (source: apps.leave, ordered by updated_at) --------


@dataclass(frozen=True)
class RecentActivityItem:
    """One row of the "recent activity" feed — a leave request whose
    lifecycle changed most recently (applied/approved/rejected/cancelled).
    See `apps.leave.domain.entities.LeaveRequest.updated_at`'s docstring for
    why ordering by this column is sufficient to build this feed with no
    dedicated audit/event-log table."""

    leave_request_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None
    employee_code: str | None
    leave_type_name: str | None
    status: str
    start_date: date
    end_date: date
    updated_at: datetime | None


# --- Upcoming Holidays (source: apps.attendance) -------------------------


@dataclass(frozen=True)
class UpcomingHoliday:
    id: uuid.UUID
    name: str
    holiday_date: date
    description: str
