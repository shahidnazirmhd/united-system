"""Adapter implementing `HolidayLookupPort` against `apps.attendance`'s
already-composed public `HolidayService` — the one file in this module
allowed to import `apps.attendance`, and even then only its public
composition root (`build_holiday_service`), never that module's
infrastructure/ORM layer directly.
"""
from __future__ import annotations

from apps.attendance.interface import dependencies as attendance_dependencies
from apps.dashboard.application.dtos import UpcomingHoliday
from apps.dashboard.application.ports import HolidayLookupPort


class HolidayServiceLookupAdapter(HolidayLookupPort):
    def get_upcoming_holidays(self, *, limit: int) -> list[UpcomingHoliday]:
        source = attendance_dependencies.build_holiday_service().list_upcoming(limit=limit)
        return [
            UpcomingHoliday(
                id=holiday.id,
                name=holiday.name,
                holiday_date=holiday.holiday_date,
                description=holiday.description,
            )
            for holiday in source
        ]
