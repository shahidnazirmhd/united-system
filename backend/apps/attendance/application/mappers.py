"""Domain entity -> response DTO mapping, shared by both the command and
query services, matching apps/employees/application/mappers.py's
identical reasoning."""
from __future__ import annotations

from apps.attendance.application.dtos import HolidayResponse
from apps.attendance.domain.entities import Holiday


def holiday_to_response(holiday: Holiday) -> HolidayResponse:
    return HolidayResponse(
        id=holiday.id,
        name=holiday.name,
        holiday_date=holiday.holiday_date,
        description=holiday.description,
        is_active=holiday.is_active,
    )
