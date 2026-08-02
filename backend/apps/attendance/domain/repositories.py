"""Repository interface for Attendance's Holiday entity — extends
shared_kernel's generic `BaseRepository`, matching
`apps.employees.domain.repositories.DepartmentRepository`'s own extension
of the same base exactly.
"""
from __future__ import annotations

from abc import abstractmethod
from datetime import date

from apps.attendance.domain.entities import Holiday
from shared_kernel.domain.repository import BaseRepository


class HolidayRepository(BaseRepository[Holiday]):
    @abstractmethod
    def exists_with_date(self, holiday_date: date) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_dates_in_range(self, *, start_date: date, end_date: date) -> frozenset[date]:
        """Every active holiday date within `[start_date, end_date]`
        (inclusive) — the exact shape Leave's working-day calculation needs
        (round 14 item 6), via this module's own `HolidayLookupPort`
        adapter (`apps.leave.infrastructure`). One query per leave
        application, not one query per calendar day."""
        raise NotImplementedError
