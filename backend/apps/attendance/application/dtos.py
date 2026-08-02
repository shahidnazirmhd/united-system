"""Input/output DTOs for Attendance's Holiday Management."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CreateHolidayRequest:
    name: str
    holiday_date: date
    description: str = ""
    created_by: uuid.UUID | None = None


@dataclass(frozen=True)
class UpdateHolidayRequest:
    holiday_id: uuid.UUID
    name: str
    holiday_date: date
    description: str = ""
    is_active: bool = True
    updated_by: uuid.UUID | None = None


@dataclass(frozen=True)
class HolidayResponse:
    id: uuid.UUID
    name: str
    holiday_date: date
    description: str
    is_active: bool


@dataclass(frozen=True)
class HolidayListQuery:
    is_active: bool | None = None
    year: int | None = None
    search: str | None = None
    ordering: tuple[str, ...] = ()
    page: int = 1
    page_size: int = 25
