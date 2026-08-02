"""Facade composing Holiday's command and query services — matching
`apps.employees.application.services.department_service`'s identical
reasoning (BaseViewSet's generic list()/retrieve() expect this facade's
shape, not either half alone)."""
from __future__ import annotations

import uuid
from datetime import date

from apps.attendance.application.dtos import (
    CreateHolidayRequest,
    HolidayListQuery,
    HolidayResponse,
    UpdateHolidayRequest,
)
from apps.attendance.application.services.holiday_command_service import HolidayCommandService
from apps.attendance.application.services.holiday_query_service import HolidayQueryService
from apps.attendance.domain.repositories import HolidayRepository
from shared_kernel.domain.repository import PageResult, QueryParams


def _coerce_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes")


def _coerce_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    return int(value)  # type: ignore[arg-type]


class HolidayService:
    def __init__(
        self,
        command_service: HolidayCommandService,
        query_service: HolidayQueryService,
        holiday_repository: HolidayRepository | None = None,
    ) -> None:
        self._commands = command_service
        self._queries = query_service
        # Optional (default None) purely so any existing test construction
        # of this facade with only the two services keeps working
        # unchanged — only get_dates_in_range (round 14's cross-module
        # read) needs direct repository access, bypassing the
        # command/query split entirely since this is an internal batch
        # read for another module, not a paginated UI list.
        self._holidays = holiday_repository

    def get_dates_in_range(self, *, start_date: date, end_date: date) -> frozenset[date]:
        assert self._holidays is not None, (
            "HolidayService.get_dates_in_range requires a HolidayRepository — "
            "see interface/dependencies.py's build_holiday_service."
        )
        return self._holidays.get_dates_in_range(start_date=start_date, end_date=end_date)

    def get_by_id(self, holiday_id: uuid.UUID) -> HolidayResponse:
        return self._queries.get_by_id(holiday_id)

    def list(self, query: HolidayListQuery | QueryParams) -> PageResult[HolidayResponse]:
        if isinstance(query, QueryParams):
            return self._queries.list(
                HolidayListQuery(
                    is_active=_coerce_bool(query.filters.get("is_active")),
                    year=_coerce_int(query.filters.get("year")),
                    search=query.search,
                    ordering=query.ordering,
                    page=query.page,
                    page_size=query.page_size,
                )
            )
        return self._queries.list(query)

    def list_upcoming(self, *, limit: int = 5) -> list[HolidayResponse]:
        return self._queries.list_upcoming(limit=limit)

    def create_holiday(self, request: CreateHolidayRequest) -> HolidayResponse:
        return self._commands.create_holiday(request)

    def update_holiday(self, request: UpdateHolidayRequest) -> HolidayResponse:
        return self._commands.update_holiday(request)
