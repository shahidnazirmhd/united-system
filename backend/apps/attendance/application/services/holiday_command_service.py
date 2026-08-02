"""Write side of Holiday Management — built on `BaseService`, matching
`apps.employees.application.services.department_command_service`'s
identical reasoning (CRUD-plus-a-validation, not genuinely distinct
use cases)."""
from __future__ import annotations

from apps.attendance.application.dtos import CreateHolidayRequest, HolidayResponse, UpdateHolidayRequest
from apps.attendance.application.mappers import holiday_to_response
from apps.attendance.application.ports import LeaveReferenceCheckPort
from apps.attendance.domain.entities import Holiday
from apps.attendance.domain.exceptions import (
    DuplicateHolidayDateError,
    HolidayNotFoundError,
    HolidayReferencedByLeaveRequestError,
)
from apps.attendance.domain.repositories import HolidayRepository
from shared_kernel.application.base_service import BaseService
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.uuid7 import generate_uuid7


class HolidayCommandService(BaseService[Holiday]):
    not_found_exception = HolidayNotFoundError

    def __init__(
        self,
        holiday_repository: HolidayRepository,
        unit_of_work: UnitOfWork,
        leave_reference_check: LeaveReferenceCheckPort,
    ) -> None:
        super().__init__(repository=holiday_repository, unit_of_work=unit_of_work)
        self._holidays = holiday_repository
        # Round 15 item 3 — see apps.attendance.application.ports
        # .LeaveReferenceCheckPort's docstring for why this reverse
        # dependency on Leave exists.
        self._leave_reference_check = leave_reference_check

    def create_holiday(self, request: CreateHolidayRequest) -> HolidayResponse:
        holiday = Holiday(
            id=generate_uuid7(),
            name=request.name,
            holiday_date=request.holiday_date,
            description=request.description,
        )
        created = self.create(holiday)  # validate_create -> uow -> repository.create
        return holiday_to_response(created)

    def update_holiday(self, request: UpdateHolidayRequest) -> HolidayResponse:
        existing = self.get_by_id(request.holiday_id)  # raises HolidayNotFoundError if missing
        # Round 15 item 3 — block ANY edit (including deactivation; this
        # endpoint has no hard delete, see the ViewSet's docstring) to a
        # holiday whose CURRENT date is still relied upon by a real
        # PENDING/APPROVED leave request. Checked against the existing
        # stored date, not the submitted one: the request being edited must
        # first be cancelled before this holiday can change at all — this
        # is also what stops a stale Leave Details read from ever being
        # computed against a holiday that quietly stopped applying.
        if self._leave_reference_check.has_active_leave_request_covering_date(existing.holiday_date):
            raise HolidayReferencedByLeaveRequestError()
        updated_entity = Holiday(
            id=request.holiday_id,
            name=request.name,
            holiday_date=request.holiday_date,
            description=request.description,
            is_active=request.is_active,
        )
        updated = self.update(updated_entity)  # validate_update -> uow -> repository.update
        return holiday_to_response(updated)

    # --- BaseService hooks ----------------------------------------------
    def validate_create(self, entity: Holiday) -> None:
        if self._holidays.exists_with_date(entity.holiday_date):
            raise DuplicateHolidayDateError()

    def validate_update(self, entity: Holiday) -> None:
        holder = self._find_by_date(entity.holiday_date)
        if holder is not None and holder.id != entity.id:
            raise DuplicateHolidayDateError()

    def _find_by_date(self, holiday_date) -> Holiday | None:
        from shared_kernel.domain.repository import QueryParams

        page = self._holidays.list(QueryParams(filters={"holiday_date": holiday_date}, page_size=1))
        return page.items[0] if page.items else None
