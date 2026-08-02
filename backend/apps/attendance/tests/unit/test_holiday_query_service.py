"""Unit tests for `HolidayQueryService` — hand-rolled fake repository, no
Django, no database. First test file for `apps.attendance`; covers both the
pre-existing `get_by_id` read and the new `list_upcoming` (Phase 14:
Dashboard) read.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from apps.attendance.application.services.holiday_query_service import HolidayQueryService
from apps.attendance.domain.entities import Holiday
from apps.attendance.domain.exceptions import HolidayNotFoundError


class FakeHolidayRepository:
    def __init__(self, holidays: list[Holiday]):
        self._holidays = {h.id: h for h in holidays}
        self.last_call = None

    def get_by_id(self, holiday_id):
        return self._holidays.get(holiday_id)

    def list_upcoming(self, *, from_date: date, limit: int) -> list[Holiday]:
        self.last_call = {"from_date": from_date, "limit": limit}
        upcoming = sorted(
            (h for h in self._holidays.values() if h.is_active and h.holiday_date >= from_date),
            key=lambda h: h.holiday_date,
        )
        return upcoming[:limit]

    # Unused by these tests, present to satisfy the interface shape.
    def list(self, query):
        raise NotImplementedError

    def create(self, entity):
        raise NotImplementedError

    def update(self, entity):
        raise NotImplementedError

    def delete(self, entity_id):
        raise NotImplementedError

    def exists(self, entity_id):
        raise NotImplementedError

    def exists_with_date(self, holiday_date):
        raise NotImplementedError

    def get_dates_in_range(self, *, start_date, end_date):
        raise NotImplementedError


def _holiday(name: str, holiday_date: date, *, is_active: bool = True) -> Holiday:
    return Holiday(id=uuid.uuid4(), name=name, holiday_date=holiday_date, description="", is_active=is_active)


def test_get_by_id_raises_when_not_found() -> None:
    service = HolidayQueryService(FakeHolidayRepository([]))

    with pytest.raises(HolidayNotFoundError):
        service.get_by_id(uuid.uuid4())


def test_list_upcoming_resolves_today_internally_and_orders_earliest_first() -> None:
    today = date.today()
    later = _holiday("Later Holiday", date(today.year + 1, 12, 31))
    sooner = _holiday("Sooner Holiday", date(today.year + 1, 1, 1))
    repository = FakeHolidayRepository([later, sooner])
    service = HolidayQueryService(repository)

    result = service.list_upcoming(limit=5)

    assert [h.name for h in result] == ["Sooner Holiday", "Later Holiday"]
    assert repository.last_call["from_date"] == today
    assert repository.last_call["limit"] == 5


def test_list_upcoming_excludes_inactive_holidays() -> None:
    today = date.today()
    inactive = _holiday("Cancelled Holiday", date(today.year + 1, 6, 1), is_active=False)
    service = HolidayQueryService(FakeHolidayRepository([inactive]))

    result = service.list_upcoming(limit=5)

    assert result == []
