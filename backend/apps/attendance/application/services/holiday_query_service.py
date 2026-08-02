"""Read side of Holiday Management — matching
`apps.employees.application.services.department_query_service`'s shape,
minus any enrichment (Holiday has no related-entity names to resolve)."""
from __future__ import annotations

import uuid
from datetime import date

from apps.attendance.application.dtos import HolidayListQuery, HolidayResponse
from apps.attendance.application.mappers import holiday_to_response
from apps.attendance.domain.exceptions import HolidayNotFoundError
from apps.attendance.domain.repositories import HolidayRepository
from shared_kernel.domain.repository import PageResult, QueryParams

_SEARCH_FIELDS = ("name",)
_DEFAULT_ORDERING = ("holiday_date",)


class HolidayQueryService:
    def __init__(self, holiday_repository: HolidayRepository) -> None:
        self._holidays = holiday_repository

    def get_by_id(self, holiday_id: uuid.UUID) -> HolidayResponse:
        holiday = self._holidays.get_by_id(holiday_id)
        if holiday is None:
            raise HolidayNotFoundError()
        return holiday_to_response(holiday)

    def list_upcoming(self, *, limit: int = 5) -> list[HolidayResponse]:
        """Phase 14 (Dashboard) — "today" is resolved here, not passed in by
        the caller, matching every other "as of right now" read in this
        codebase (e.g. `LeaveRequestService.get_statistics`'s own
        `date.today()` call)."""
        holidays = self._holidays.list_upcoming(from_date=date.today(), limit=limit)
        return [holiday_to_response(h) for h in holidays]

    def list(self, query: HolidayListQuery) -> PageResult[HolidayResponse]:
        filters: dict[str, object] = {}
        if query.is_active is not None:
            filters["is_active"] = query.is_active
        if query.year is not None:
            filters["holiday_date__year"] = query.year

        page_result = self._holidays.list(
            QueryParams(
                filters=filters,
                search=query.search,
                search_fields=_SEARCH_FIELDS,
                ordering=query.ordering or _DEFAULT_ORDERING,
                page=query.page,
                page_size=query.page_size,
            )
        )
        return PageResult(
            items=[holiday_to_response(h) for h in page_result.items],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )
