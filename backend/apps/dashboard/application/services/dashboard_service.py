"""Dashboard's only service — a thin read facade delegating to its three
ports. No business logic to speak of (see `domain/__init__.py`'s docstring
for why): each method is a one-line delegation, kept as separate methods
(rather than one mega "get everything" call) so each frontend widget can
fetch, cache, and poll independently at its own `refetchInterval` — the
"generic/modular, widgets addable independently" requirement Phase 14 asks
for.
"""
from __future__ import annotations

from apps.dashboard.application.dtos import (
    EmployeeStatisticsResponse,
    LeaveStatisticsResponse,
    RecentActivityItem,
    UpcomingHoliday,
)
from apps.dashboard.application.ports import (
    EmployeeStatisticsPort,
    HolidayLookupPort,
    LeaveStatisticsPort,
)

_DEFAULT_RECENT_ACTIVITY_LIMIT = 10
_DEFAULT_UPCOMING_HOLIDAYS_LIMIT = 5


class DashboardService:
    def __init__(
        self,
        employee_statistics: EmployeeStatisticsPort,
        leave_statistics: LeaveStatisticsPort,
        holiday_lookup: HolidayLookupPort,
    ) -> None:
        self._employee_statistics = employee_statistics
        self._leave_statistics = leave_statistics
        self._holiday_lookup = holiday_lookup

    def get_employee_statistics(self) -> EmployeeStatisticsResponse:
        return self._employee_statistics.get_statistics()

    def get_leave_statistics(self) -> LeaveStatisticsResponse:
        return self._leave_statistics.get_statistics()

    def get_recent_activity(
        self, *, limit: int = _DEFAULT_RECENT_ACTIVITY_LIMIT
    ) -> list[RecentActivityItem]:
        return self._leave_statistics.get_recent_activity(limit=limit)

    def get_upcoming_holidays(
        self, *, limit: int = _DEFAULT_UPCOMING_HOLIDAYS_LIMIT
    ) -> list[UpcomingHoliday]:
        return self._holiday_lookup.get_upcoming_holidays(limit=limit)
