"""Unit tests for `DashboardService` — the thin read facade. Fake ports
only; no Django, no database, and no dependency on Employees/Leave/
Attendance's own internals — same discipline as
`apps.approvals.tests.unit.test_approval_service`'s fake-port pattern,
applied to a pure facade with no business logic of its own to speak of.
"""
from __future__ import annotations

import uuid
from datetime import date

from apps.dashboard.application.dtos import (
    EmployeeStatisticsResponse,
    LeaveStatisticsResponse,
    RecentActivityItem,
    UpcomingHoliday,
)
from apps.dashboard.application.services.dashboard_service import DashboardService


class FakeEmployeeStatisticsPort:
    def __init__(self, response: EmployeeStatisticsResponse):
        self._response = response
        self.calls = 0

    def get_statistics(self) -> EmployeeStatisticsResponse:
        self.calls += 1
        return self._response


class FakeLeaveStatisticsPort:
    def __init__(self, statistics: LeaveStatisticsResponse, activity: list[RecentActivityItem]):
        self._statistics = statistics
        self._activity = activity
        self.recent_activity_limit_calls: list[int] = []

    def get_statistics(self) -> LeaveStatisticsResponse:
        return self._statistics

    def get_recent_activity(self, *, limit: int) -> list[RecentActivityItem]:
        self.recent_activity_limit_calls.append(limit)
        return self._activity[:limit]


class FakeHolidayLookupPort:
    def __init__(self, holidays: list[UpcomingHoliday]):
        self._holidays = holidays
        self.limit_calls: list[int] = []

    def get_upcoming_holidays(self, *, limit: int) -> list[UpcomingHoliday]:
        self.limit_calls.append(limit)
        return self._holidays[:limit]


def _employee_statistics() -> EmployeeStatisticsResponse:
    return EmployeeStatisticsResponse(
        total_employees=5,
        active_count=4,
        inactive_count=0,
        terminated_count=1,
        status_breakdown={"active": 4, "terminated": 1},
        current_status_breakdown={"working": 4},
        employment_type_breakdown={"full_time": 5},
        department_breakdown=[],
        new_hires_this_month=1,
    )


def _leave_statistics() -> LeaveStatisticsResponse:
    return LeaveStatisticsResponse(
        status_breakdown={"approved": 2},
        leave_type_breakdown=[],
        monthly_trend=[],
        on_leave_today_count=1,
    )


def _recent_activity_item() -> RecentActivityItem:
    return RecentActivityItem(
        leave_request_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        employee_name="Ada Lovelace",
        employee_code="E001",
        leave_type_name="Annual Leave",
        status="approved",
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 3),
        updated_at=None,
    )


def _upcoming_holiday() -> UpcomingHoliday:
    return UpcomingHoliday(id=uuid.uuid4(), name="Independence Day", holiday_date=date(2026, 8, 15), description="")


def _build_service(
    *,
    employee_statistics: EmployeeStatisticsResponse | None = None,
    leave_statistics: LeaveStatisticsResponse | None = None,
    recent_activity: list[RecentActivityItem] | None = None,
    upcoming_holidays: list[UpcomingHoliday] | None = None,
) -> tuple[DashboardService, FakeEmployeeStatisticsPort, FakeLeaveStatisticsPort, FakeHolidayLookupPort]:
    employee_port = FakeEmployeeStatisticsPort(employee_statistics or _employee_statistics())
    leave_port = FakeLeaveStatisticsPort(leave_statistics or _leave_statistics(), recent_activity or [])
    holiday_port = FakeHolidayLookupPort(upcoming_holidays or [])
    service = DashboardService(
        employee_statistics=employee_port, leave_statistics=leave_port, holiday_lookup=holiday_port
    )
    return service, employee_port, leave_port, holiday_port


def test_get_employee_statistics_delegates_to_its_port() -> None:
    expected = _employee_statistics()
    service, employee_port, _, _ = _build_service(employee_statistics=expected)

    result = service.get_employee_statistics()

    assert result is expected
    assert employee_port.calls == 1


def test_get_leave_statistics_delegates_to_its_port() -> None:
    expected = _leave_statistics()
    service, _, _, _ = _build_service(leave_statistics=expected)

    assert service.get_leave_statistics() is expected


def test_get_recent_activity_uses_the_default_limit_when_not_specified() -> None:
    activity = [_recent_activity_item() for _ in range(3)]
    service, _, leave_port, _ = _build_service(recent_activity=activity)

    result = service.get_recent_activity()

    assert result == activity
    assert leave_port.recent_activity_limit_calls == [10]


def test_get_recent_activity_forwards_a_custom_limit() -> None:
    activity = [_recent_activity_item() for _ in range(3)]
    service, _, leave_port, _ = _build_service(recent_activity=activity)

    result = service.get_recent_activity(limit=2)

    assert len(result) == 2
    assert leave_port.recent_activity_limit_calls == [2]


def test_get_upcoming_holidays_uses_the_default_limit_when_not_specified() -> None:
    holidays = [_upcoming_holiday() for _ in range(2)]
    service, _, _, holiday_port = _build_service(upcoming_holidays=holidays)

    result = service.get_upcoming_holidays()

    assert result == holidays
    assert holiday_port.limit_calls == [5]


def test_get_upcoming_holidays_forwards_a_custom_limit() -> None:
    holidays = [_upcoming_holiday() for _ in range(2)]
    service, _, _, holiday_port = _build_service(upcoming_holidays=holidays)

    service.get_upcoming_holidays(limit=1)

    assert holiday_port.limit_calls == [1]
