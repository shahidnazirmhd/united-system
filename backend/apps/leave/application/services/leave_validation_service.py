"""Business validation logic for Leave, isolated in its own service per the
brief's explicit "Business logic must exist only in Services" requirement
and Single Responsibility — `LeaveRequestService` orchestrates persistence
and events, this class only decides yes/no (and raises the specific
`DomainError` subclass when the answer is no). Every method either returns
normally or raises; none of them touch a repository's write methods.

`allow_past_start_date` is injected by the constructor rather than this
class reaching into `django.conf.settings` itself — the application layer
must stay framework-independent (no Django import anywhere under
`application/`, matching every other module's discipline), so reading
`settings.LEAVE_ALLOW_PAST_START_DATE` is `interface/dependencies.py`'s job
(the composition root, the one place already trusted to read Django
settings — see e.g. `apps.employees.interface.dependencies._build_email_client`
doing the same for `SMTP_HOST`). This also makes the flag trivial to unit
test without a Django settings module configured at all.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from apps.leave.application.ports import EmployeeLookupPort
from apps.leave.domain.entities import LeaveType
from apps.leave.domain.exceptions import (
    DuplicateLeaveRequestError,
    InsufficientLeaveBalanceError,
    InvalidLeaveDateRangeError,
    LeaveEmployeeNotFoundError,
    LeaveTypeNotFoundError,
    OverlappingLeaveRequestError,
    PastLeaveStartDateError,
)
from apps.leave.domain.repositories import LeaveBalanceRepository, LeaveRequestRepository, LeaveTypeRepository
from shared_kernel.domain.value_objects import DateRange


class LeaveValidationService:
    def __init__(
        self,
        leave_type_repository: LeaveTypeRepository,
        leave_balance_repository: LeaveBalanceRepository,
        leave_request_repository: LeaveRequestRepository,
        employee_lookup: EmployeeLookupPort,
        allow_past_start_date: bool = False,
    ) -> None:
        self._leave_types = leave_type_repository
        self._balances = leave_balance_repository
        self._requests = leave_request_repository
        self._employees = employee_lookup
        self._allow_past_start_date = allow_past_start_date

    def validate_employee_exists(self, employee_id: uuid.UUID) -> None:
        if not self._employees.employee_exists(employee_id):
            raise LeaveEmployeeNotFoundError()

    def validate_and_get_leave_type(self, leave_type_id: uuid.UUID) -> LeaveType:
        leave_type = self._leave_types.get_by_id(leave_type_id)
        if leave_type is None or not leave_type.is_active:
            raise LeaveTypeNotFoundError()
        return leave_type

    def build_date_range(self, start_date: date, end_date: date) -> DateRange:
        try:
            return DateRange(start_date=start_date, end_date=end_date)
        except ValueError as exc:
            raise InvalidLeaveDateRangeError(str(exc)) from exc

    def validate_not_past(self, start_date: date, *, today: date | None = None) -> None:
        if self._allow_past_start_date:
            return
        effective_today = today if today is not None else date.today()
        if start_date < effective_today:
            raise PastLeaveStartDateError()

    def validate_no_duplicate(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, date_range: DateRange
    ) -> None:
        duplicate = self._requests.get_duplicate(
            employee_id=employee_id, leave_type_id=leave_type_id, date_range=date_range
        )
        if duplicate is not None:
            raise DuplicateLeaveRequestError()

    def validate_no_overlap(
        self, *, employee_id: uuid.UUID, date_range: DateRange, exclude_request_id: uuid.UUID | None = None
    ) -> None:
        overlapping = self._requests.get_overlapping_for_employee(
            employee_id=employee_id, date_range=date_range, exclude_request_id=exclude_request_id
        )
        if overlapping:
            raise OverlappingLeaveRequestError()

    def validate_sufficient_balance(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int, requested_days: Decimal
    ) -> None:
        balance = self._balances.get_by_employee_leave_type_year(
            employee_id=employee_id, leave_type_id=leave_type_id, year=year
        )
        # No balance row at all is treated as zero entitlement, not a
        # separate error path — see LeaveBalanceService.get_balance's
        # docstring for the same judgment call made on the read side.
        available = balance.available_days if balance is not None else Decimal("0")
        already_pending = self._requests.sum_pending_days(
            employee_id=employee_id, leave_type_id=leave_type_id, year=year
        )
        if (available - already_pending) < requested_days:
            raise InsufficientLeaveBalanceError()
