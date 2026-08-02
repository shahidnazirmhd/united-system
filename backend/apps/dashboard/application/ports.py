"""Outbound ports for the Dashboard application layer.

Dashboard depends on three existing modules (Employees, Leave, Attendance)
purely for reads. Following the exact "the consumer owns the port" rule
already established by `apps.leave.application.ports.EmployeeLookupPort` /
`HolidayLookupPort` / `SettingsLookupPort`, Dashboard defines these ports in
its own vocabulary (see `application/dtos.py`), and the concrete adapters
(`infrastructure/*_adapter.py`) are the only files in this module allowed to
import another module's code — and even then, only that module's public
`interface/dependencies.py` composition root, never its infrastructure/ORM
layer directly. None of Employees/Leave/Attendance needed a single line
changed to support Dashboard (beyond each module's own additive
`get_statistics`/`list_upcoming` read method, added because each module
owns the decision of what its own statistics mean).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from apps.dashboard.application.dtos import (
    EmployeeStatisticsResponse,
    LeaveStatisticsResponse,
    RecentActivityItem,
    UpcomingHoliday,
)


class EmployeeStatisticsPort(ABC):
    @abstractmethod
    def get_statistics(self) -> EmployeeStatisticsResponse:
        """Aggregate headcount/status/department counts — backs the
        Dashboard's Employee Statistics / Department Statistics widgets."""
        raise NotImplementedError


class LeaveStatisticsPort(ABC):
    @abstractmethod
    def get_statistics(self) -> LeaveStatisticsResponse:
        """Aggregate leave counts (status/type/monthly trend/on-leave-today)
        — backs the Dashboard's Leave Statistics charts."""
        raise NotImplementedError

    @abstractmethod
    def get_recent_activity(self, *, limit: int) -> list[RecentActivityItem]:
        """The `limit` most recently changed leave requests, newest first —
        backs the Dashboard's Recent Activity widget."""
        raise NotImplementedError


class HolidayLookupPort(ABC):
    @abstractmethod
    def get_upcoming_holidays(self, *, limit: int) -> list[UpcomingHoliday]:
        """The `limit` next active holidays on or after today, earliest
        first — backs the Dashboard's Upcoming Holidays widget."""
        raise NotImplementedError
