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

    @abstractmethod
    def list_upcoming(self, *, from_date: date, limit: int) -> list[Holiday]:
        """Every active holiday on or after `from_date`, earliest first,
        capped at `limit` — Phase 14 (Dashboard)'s "Upcoming Holidays"
        widget, via this module's own `HolidayLookupPort` adapter
        (`apps.dashboard.infrastructure`). A dedicated method rather than
        reusing the generic `list()` with a raw `holiday_date__gte` filter:
        `HolidayQueryService.list()`'s own `HolidayListQuery` DTO only
        exposes `is_active`/`year`/`search`/`ordering` (see that service's
        docstring) — deliberately not a grab-bag of arbitrary ORM lookup
        strings a caller could pass through, so "what does upcoming mean"
        stays this module's own decision, expressed as a named method."""
        raise NotImplementedError
