"""Unit tests for LeaveValidationService — every dependency is a hand-rolled
fake, no Django, no database. Same discipline as
apps/employees/tests/unit/test_employee_telegram_linking_service.py.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.leave.application.services.leave_validation_service import LeaveValidationService
from apps.leave.domain.entities import LeaveBalance, LeaveRequest, LeaveType
from apps.leave.domain.enums import LeaveRequestStatus
from apps.leave.domain.exceptions import (
    DuplicateLeaveRequestError,
    InsufficientLeaveBalanceError,
    InvalidLeaveDateRangeError,
    LeaveEmployeeNotFoundError,
    LeaveTypeNotFoundError,
    ManagerNotLinkedToTelegramError,
    NoManagerAssignedError,
    OverlappingLeaveRequestError,
    PastLeaveStartDateError,
)
from shared_kernel.domain.value_objects import DateRange


class FakeEmployeeLookupPort:
    def __init__(
        self,
        existing_employee_ids: set[uuid.UUID] | None = None,
        *,
        managers: dict[uuid.UUID, uuid.UUID | None] | None = None,
        telegram_linked_employee_ids: set[uuid.UUID] | None = None,
    ):
        self._existing = existing_employee_ids or set()
        self._managers = managers or {}
        self._telegram_linked = telegram_linked_employee_ids or set()

    def employee_exists(self, employee_id):
        return employee_id in self._existing

    def get_employee_id_by_user_id(self, user_id):
        raise NotImplementedError("not exercised by these tests")

    def get_employee_id_by_telegram_user_id(self, telegram_user_id):
        raise NotImplementedError("not exercised by these tests")

    def get_manager_employee_id(self, employee_id):
        return self._managers.get(employee_id)

    def is_employee_linked_to_telegram(self, employee_id):
        return employee_id in self._telegram_linked


class FakeLeaveTypeRepository:
    def __init__(self, leave_types: list[LeaveType] | None = None):
        self._by_id = {lt.id: lt for lt in (leave_types or [])}

    def get_by_id(self, leave_type_id):
        return self._by_id.get(leave_type_id)

    def get_by_code(self, code):
        return next((lt for lt in self._by_id.values() if lt.code == code), None)

    def list_active(self):
        return [lt for lt in self._by_id.values() if lt.is_active]

    def exists(self, leave_type_id):
        lt = self._by_id.get(leave_type_id)
        return lt is not None and lt.is_active


class FakeLeaveBalanceRepository:
    def __init__(self, balances: list[LeaveBalance] | None = None):
        self._balances = list(balances or [])

    def get_by_employee_leave_type_year(self, *, employee_id, leave_type_id, year):
        return next(
            (
                b
                for b in self._balances
                if b.employee_id == employee_id and b.leave_type_id == leave_type_id and b.year == year
            ),
            None,
        )

    def list_by_employee(self, *, employee_id, year):
        return [b for b in self._balances if b.employee_id == employee_id and b.year == year]

    def get_by_id(self, entity_id):
        return next((b for b in self._balances if b.id == entity_id), None)

    def list(self, query):
        raise NotImplementedError("not exercised by these tests")

    def create(self, entity):
        self._balances.append(entity)
        return entity

    def update(self, entity):
        self._balances = [entity if b.id == entity.id else b for b in self._balances]
        return entity

    def delete(self, entity_id):
        self._balances = [b for b in self._balances if b.id != entity_id]

    def exists(self, entity_id):
        return any(b.id == entity_id for b in self._balances)


class FakeLeaveRequestRepository:
    def __init__(self, requests: list[LeaveRequest] | None = None):
        self._requests = list(requests or [])

    def get_overlapping_for_employee(self, *, employee_id, date_range, exclude_request_id=None):
        active = (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED)
        return [
            r
            for r in self._requests
            if r.employee_id == employee_id
            and r.status in active
            and r.id != exclude_request_id
            and r.date_range.overlaps(date_range)
        ]

    def get_duplicate(self, *, employee_id, leave_type_id, date_range):
        active = (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED)
        return next(
            (
                r
                for r in self._requests
                if r.employee_id == employee_id
                and r.leave_type_id == leave_type_id
                and r.status in active
                and r.date_range.start_date == date_range.start_date
                and r.date_range.end_date == date_range.end_date
            ),
            None,
        )

    def sum_pending_days(self, *, employee_id, leave_type_id, year):
        return sum(
            (
                r.total_days
                for r in self._requests
                if r.employee_id == employee_id
                and r.leave_type_id == leave_type_id
                and r.status == LeaveRequestStatus.PENDING
                and r.date_range.start_date.year == year
            ),
            Decimal("0"),
        )

    def get_by_id(self, entity_id):
        return next((r for r in self._requests if r.id == entity_id), None)

    def list(self, query):
        raise NotImplementedError("not exercised by these tests")

    def create(self, entity):
        self._requests.append(entity)
        return entity

    def update(self, entity):
        self._requests = [entity if r.id == entity.id else r for r in self._requests]
        return entity

    def delete(self, entity_id):
        self._requests = [r for r in self._requests if r.id != entity_id]

    def exists(self, entity_id):
        return any(r.id == entity_id for r in self._requests)


def _leave_type(**overrides) -> LeaveType:
    return LeaveType(
        id=overrides.pop("id", uuid.uuid4()),
        name=overrides.pop("name", "Annual Leave"),
        code=overrides.pop("code", "ANNUAL"),
        default_annual_days=overrides.pop("default_annual_days", Decimal("20")),
        is_active=overrides.pop("is_active", True),
    )


def _service(
    employee_exists=True, leave_types=None, balances=None, requests=None, allow_past_start_date=False
) -> LeaveValidationService:
    employee_id_set = set()
    return LeaveValidationService(
        leave_type_repository=FakeLeaveTypeRepository(leave_types or []),
        leave_balance_repository=FakeLeaveBalanceRepository(balances or []),
        leave_request_repository=FakeLeaveRequestRepository(requests or []),
        employee_lookup=FakeEmployeeLookupPort(employee_id_set),
        allow_past_start_date=allow_past_start_date,
    )


# --- validate_employee_exists -------------------------------------------


def test_validate_employee_exists_raises_for_unknown_employee() -> None:
    service = LeaveValidationService(
        leave_type_repository=FakeLeaveTypeRepository(),
        leave_balance_repository=FakeLeaveBalanceRepository(),
        leave_request_repository=FakeLeaveRequestRepository(),
        employee_lookup=FakeEmployeeLookupPort(set()),
    )

    with pytest.raises(LeaveEmployeeNotFoundError):
        service.validate_employee_exists(uuid.uuid4())


def test_validate_employee_exists_passes_for_known_employee() -> None:
    employee_id = uuid.uuid4()
    service = LeaveValidationService(
        leave_type_repository=FakeLeaveTypeRepository(),
        leave_balance_repository=FakeLeaveBalanceRepository(),
        leave_request_repository=FakeLeaveRequestRepository(),
        employee_lookup=FakeEmployeeLookupPort({employee_id}),
    )

    service.validate_employee_exists(employee_id)  # does not raise


# --- validate_manager_available_for_approval (Approval Engine, Phase 9) --


def test_validate_manager_available_for_approval_raises_when_no_manager_assigned() -> None:
    employee_id = uuid.uuid4()
    service = LeaveValidationService(
        leave_type_repository=FakeLeaveTypeRepository(),
        leave_balance_repository=FakeLeaveBalanceRepository(),
        leave_request_repository=FakeLeaveRequestRepository(),
        employee_lookup=FakeEmployeeLookupPort({employee_id}, managers={employee_id: None}),
    )

    with pytest.raises(NoManagerAssignedError):
        service.validate_manager_available_for_approval(employee_id)


def test_validate_manager_available_for_approval_raises_when_manager_not_linked_to_telegram() -> None:
    employee_id, manager_id = uuid.uuid4(), uuid.uuid4()
    service = LeaveValidationService(
        leave_type_repository=FakeLeaveTypeRepository(),
        leave_balance_repository=FakeLeaveBalanceRepository(),
        leave_request_repository=FakeLeaveRequestRepository(),
        employee_lookup=FakeEmployeeLookupPort(
            {employee_id}, managers={employee_id: manager_id}, telegram_linked_employee_ids=set()
        ),
    )

    with pytest.raises(ManagerNotLinkedToTelegramError):
        service.validate_manager_available_for_approval(employee_id)


def test_validate_manager_available_for_approval_passes_when_manager_linked_to_telegram() -> None:
    employee_id, manager_id = uuid.uuid4(), uuid.uuid4()
    service = LeaveValidationService(
        leave_type_repository=FakeLeaveTypeRepository(),
        leave_balance_repository=FakeLeaveBalanceRepository(),
        leave_request_repository=FakeLeaveRequestRepository(),
        employee_lookup=FakeEmployeeLookupPort(
            {employee_id}, managers={employee_id: manager_id}, telegram_linked_employee_ids={manager_id}
        ),
    )

    service.validate_manager_available_for_approval(employee_id)  # does not raise


# --- validate_and_get_leave_type -----------------------------------------


def test_validate_and_get_leave_type_raises_for_unknown_type() -> None:
    service = _service()

    with pytest.raises(LeaveTypeNotFoundError):
        service.validate_and_get_leave_type(uuid.uuid4())


def test_validate_and_get_leave_type_raises_for_inactive_type() -> None:
    leave_type = _leave_type(is_active=False)
    service = _service(leave_types=[leave_type])

    with pytest.raises(LeaveTypeNotFoundError):
        service.validate_and_get_leave_type(leave_type.id)


def test_validate_and_get_leave_type_returns_active_type() -> None:
    leave_type = _leave_type()
    service = _service(leave_types=[leave_type])

    result = service.validate_and_get_leave_type(leave_type.id)

    assert result.id == leave_type.id


# --- build_date_range ------------------------------------------------


def test_build_date_range_raises_when_end_before_start() -> None:
    service = _service()

    with pytest.raises(InvalidLeaveDateRangeError):
        service.build_date_range(date(2026, 8, 10), date(2026, 8, 5))


def test_build_date_range_returns_valid_range() -> None:
    service = _service()

    result = service.build_date_range(date(2026, 8, 5), date(2026, 8, 10))

    assert result == DateRange(start_date=date(2026, 8, 5), end_date=date(2026, 8, 10))


# --- validate_not_past ------------------------------------------------


def test_validate_not_past_raises_for_past_start_date_by_default() -> None:
    service = _service(allow_past_start_date=False)
    yesterday = date.today() - timedelta(days=1)

    with pytest.raises(PastLeaveStartDateError):
        service.validate_not_past(yesterday)


def test_validate_not_past_allows_past_start_date_when_configured() -> None:
    service = _service(allow_past_start_date=True)
    yesterday = date.today() - timedelta(days=1)

    service.validate_not_past(yesterday)  # does not raise


def test_validate_not_past_allows_future_start_date() -> None:
    service = _service()
    tomorrow = date.today() + timedelta(days=1)

    service.validate_not_past(tomorrow)  # does not raise


# --- validate_no_duplicate / validate_no_overlap -----------------------


def _existing_request(employee_id, leave_type_id, start, end, status=LeaveRequestStatus.PENDING) -> LeaveRequest:
    return LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        date_range=DateRange(start_date=start, end_date=end),
        status=status,
    )


def test_validate_no_duplicate_raises_for_exact_match() -> None:
    employee_id, leave_type_id = uuid.uuid4(), uuid.uuid4()
    existing = _existing_request(employee_id, leave_type_id, date(2026, 8, 1), date(2026, 8, 3))
    service = _service(requests=[existing])

    with pytest.raises(DuplicateLeaveRequestError):
        service.validate_no_duplicate(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            date_range=DateRange(start_date=date(2026, 8, 1), end_date=date(2026, 8, 3)),
        )


def test_validate_no_duplicate_ignores_cancelled_requests() -> None:
    employee_id, leave_type_id = uuid.uuid4(), uuid.uuid4()
    existing = _existing_request(
        employee_id, leave_type_id, date(2026, 8, 1), date(2026, 8, 3), status=LeaveRequestStatus.CANCELLED
    )
    service = _service(requests=[existing])

    service.validate_no_duplicate(
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        date_range=DateRange(start_date=date(2026, 8, 1), end_date=date(2026, 8, 3)),
    )  # does not raise


def test_validate_no_overlap_raises_for_overlapping_dates_any_leave_type() -> None:
    employee_id = uuid.uuid4()
    existing = _existing_request(employee_id, uuid.uuid4(), date(2026, 8, 1), date(2026, 8, 5))
    service = _service(requests=[existing])

    with pytest.raises(OverlappingLeaveRequestError):
        service.validate_no_overlap(
            employee_id=employee_id, date_range=DateRange(start_date=date(2026, 8, 4), end_date=date(2026, 8, 10))
        )


def test_validate_no_overlap_allows_non_overlapping_dates() -> None:
    employee_id = uuid.uuid4()
    existing = _existing_request(employee_id, uuid.uuid4(), date(2026, 8, 1), date(2026, 8, 5))
    service = _service(requests=[existing])

    service.validate_no_overlap(
        employee_id=employee_id, date_range=DateRange(start_date=date(2026, 8, 6), end_date=date(2026, 8, 10))
    )  # does not raise


# --- validate_sufficient_balance -----------------------------------------


def test_validate_sufficient_balance_raises_when_no_balance_row_exists() -> None:
    service = _service()

    with pytest.raises(InsufficientLeaveBalanceError):
        service.validate_sufficient_balance(
            employee_id=uuid.uuid4(), leave_type_id=uuid.uuid4(), year=2026, requested_days=Decimal("1")
        )


def test_validate_sufficient_balance_passes_when_enough_available() -> None:
    employee_id, leave_type_id = uuid.uuid4(), uuid.uuid4()
    balance = LeaveBalance(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=2026,
        entitled_days=Decimal("20"),
        used_days=Decimal("5"),
    )
    service = _service(balances=[balance])

    service.validate_sufficient_balance(
        employee_id=employee_id, leave_type_id=leave_type_id, year=2026, requested_days=Decimal("10")
    )  # does not raise


def test_validate_sufficient_balance_accounts_for_already_pending_requests() -> None:
    employee_id, leave_type_id = uuid.uuid4(), uuid.uuid4()
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type_id, year=2026, entitled_days=Decimal("10")
    )
    already_pending = _existing_request(employee_id, leave_type_id, date(2026, 3, 1), date(2026, 3, 5))  # 5 days
    service = _service(balances=[balance], requests=[already_pending])

    # 10 entitled - 5 already pending = 5 left; requesting 6 more must fail.
    with pytest.raises(InsufficientLeaveBalanceError):
        service.validate_sufficient_balance(
            employee_id=employee_id, leave_type_id=leave_type_id, year=2026, requested_days=Decimal("6")
        )

    # Requesting exactly the remaining 5 must succeed.
    service.validate_sufficient_balance(
        employee_id=employee_id, leave_type_id=leave_type_id, year=2026, requested_days=Decimal("5")
    )


def test_validate_sufficient_balance_does_not_double_count_approved_requests() -> None:
    """APPROVED requests are already reflected in `used_days` — they must
    NOT also be subtracted via sum_pending_days (that would double-count)."""
    employee_id, leave_type_id = uuid.uuid4(), uuid.uuid4()
    balance = LeaveBalance(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        year=2026,
        entitled_days=Decimal("10"),
        used_days=Decimal("5"),  # an approved 5-day request already consumed this
    )
    approved = _existing_request(
        employee_id, leave_type_id, date(2026, 3, 1), date(2026, 3, 5), status=LeaveRequestStatus.APPROVED
    )
    service = _service(balances=[balance], requests=[approved])

    # available = 10 - 5 = 5; sum_pending_days excludes the APPROVED request
    # entirely, so requesting the remaining 5 days must succeed.
    service.validate_sufficient_balance(
        employee_id=employee_id, leave_type_id=leave_type_id, year=2026, requested_days=Decimal("5")
    )
