"""Unit tests for LeaveRequestService — the orchestrator. Composed with the
*real* LeaveValidationService/LeaveBalanceService (only their repository
dependencies are faked), so these tests exercise the whole apply/cancel/
approve/reject flow end-to-end at the application layer, with no Django and
no database.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.leave.application.dtos import (
    ApplyLeaveRequest,
    ApproveLeaveRequest,
    CancelLeaveRequest,
    RejectLeaveRequest,
)
from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.application.services.leave_request_service import LeaveRequestService
from apps.leave.application.services.leave_validation_service import LeaveValidationService
from apps.leave.domain.entities import LeaveBalance, LeaveRequest, LeaveType
from apps.leave.domain.enums import LeaveRequestStatus
from apps.leave.domain.events import LeaveRequestApplied, LeaveRequestApproved, LeaveRequestCancelled, LeaveRequestRejected
from apps.leave.domain.exceptions import (
    InsufficientLeaveBalanceError,
    LeaveEmployeeNotFoundError,
    LeaveRequestNotCancellableError,
    LeaveRequestNotFoundError,
    LeaveRequestOwnershipError,
    OverlappingLeaveRequestError,
)
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.value_objects import DateRange


class FakeUnitOfWork(UnitOfWork):
    def commit(self):
        pass

    def rollback(self):
        pass


class FakeEventBus(EventBus):
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)

    def subscribe(self, event_type, handler):
        pass


class FakeEmployeeLookupPort:
    def __init__(self, existing_employee_ids=None):
        self._existing = existing_employee_ids or set()

    def employee_exists(self, employee_id):
        return employee_id in self._existing

    def get_employee_id_by_user_id(self, user_id):
        raise NotImplementedError

    def get_employee_id_by_telegram_user_id(self, telegram_user_id):
        raise NotImplementedError


class FakeLeaveTypeRepository:
    def __init__(self, leave_types=None):
        self._leave_types = list(leave_types or [])

    def get_by_id(self, leave_type_id):
        return next((lt for lt in self._leave_types if lt.id == leave_type_id), None)

    def get_by_code(self, code):
        return next((lt for lt in self._leave_types if lt.code == code), None)

    def list_active(self):
        return [lt for lt in self._leave_types if lt.is_active]

    def exists(self, leave_type_id):
        return any(lt.id == leave_type_id and lt.is_active for lt in self._leave_types)


class FakeLeaveBalanceRepository:
    def __init__(self, balances=None):
        self._balances = list(balances or [])

    def get_by_employee_leave_type_year(self, *, employee_id, leave_type_id, year):
        return next(
            (b for b in self._balances if b.employee_id == employee_id and b.leave_type_id == leave_type_id and b.year == year),
            None,
        )

    def list_by_employee(self, *, employee_id, year):
        return [b for b in self._balances if b.employee_id == employee_id and b.year == year]

    def get_by_id(self, entity_id):
        return next((b for b in self._balances if b.id == entity_id), None)

    def list(self, query):
        raise NotImplementedError

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
    def __init__(self, requests=None):
        self._requests = list(requests or [])

    def get_overlapping_for_employee(self, *, employee_id, date_range, exclude_request_id=None):
        active = (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED)
        return [
            r
            for r in self._requests
            if r.employee_id == employee_id and r.status in active and r.id != exclude_request_id and r.date_range.overlaps(date_range)
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
        raise NotImplementedError

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


def _build(
    *, employee_ids=None, leave_types=None, balances=None, requests=None
) -> tuple[LeaveRequestService, FakeLeaveRequestRepository, FakeLeaveBalanceRepository, FakeEventBus]:
    leave_type_repo = FakeLeaveTypeRepository(leave_types or [])
    balance_repo = FakeLeaveBalanceRepository(balances or [])
    request_repo = FakeLeaveRequestRepository(requests or [])
    validation = LeaveValidationService(
        leave_type_repository=leave_type_repo,
        leave_balance_repository=balance_repo,
        leave_request_repository=request_repo,
        employee_lookup=FakeEmployeeLookupPort(employee_ids or set()),
    )
    balance_service = LeaveBalanceService(
        leave_balance_repository=balance_repo,
        leave_type_repository=leave_type_repo,
        leave_request_repository=request_repo,
        unit_of_work=FakeUnitOfWork(),
    )
    event_bus = FakeEventBus()
    service = LeaveRequestService(
        leave_request_repository=request_repo,
        leave_type_repository=leave_type_repo,
        validation_service=validation,
        balance_service=balance_service,
        unit_of_work=FakeUnitOfWork(),
        event_bus=event_bus,
    )
    return service, request_repo, balance_repo, event_bus


# --- apply_leave --------------------------------------------------------


def test_apply_leave_creates_pending_request_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=date.today().year + 1, entitled_days=Decimal("20")
    )
    service, requests, _balances, event_bus = _build(employee_ids={employee_id}, leave_types=[leave_type], balances=[balance])
    start = date(date.today().year + 1, 6, 1)
    end = date(date.today().year + 1, 6, 3)

    result = service.apply_leave(
        ApplyLeaveRequest(employee_id=employee_id, leave_type_id=leave_type.id, start_date=start, end_date=end, reason="Vacation")
    )

    assert result.status == "pending"
    assert result.total_days == Decimal("3")
    assert len(requests._requests) == 1
    assert any(isinstance(e, LeaveRequestApplied) for e in event_bus.published)


def test_apply_leave_raises_for_unknown_employee() -> None:
    leave_type = _leave_type()
    service, *_ = _build(employee_ids=set(), leave_types=[leave_type])

    with pytest.raises(LeaveEmployeeNotFoundError):
        service.apply_leave(
            ApplyLeaveRequest(
                employee_id=uuid.uuid4(),
                leave_type_id=leave_type.id,
                start_date=date.today() + timedelta(days=5),
                end_date=date.today() + timedelta(days=6),
            )
        )


def test_apply_leave_raises_for_insufficient_balance() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=date.today().year + 1, entitled_days=Decimal("1")
    )
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], balances=[balance])

    with pytest.raises(InsufficientLeaveBalanceError):
        service.apply_leave(
            ApplyLeaveRequest(
                employee_id=employee_id,
                leave_type_id=leave_type.id,
                start_date=date(date.today().year + 1, 6, 1),
                end_date=date(date.today().year + 1, 6, 5),  # 5 days requested, only 1 entitled
            )
        )


def test_apply_leave_raises_for_overlapping_existing_request() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    existing = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 5)),
        status=LeaveRequestStatus.PENDING,
    )
    balance = LeaveBalance(id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("30"))
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[existing])

    with pytest.raises(OverlappingLeaveRequestError):
        service.apply_leave(
            ApplyLeaveRequest(employee_id=employee_id, leave_type_id=leave_type.id, start_date=date(year, 6, 4), end_date=date(year, 6, 8))
        )


# --- cancel_leave --------------------------------------------------------


def test_cancel_leave_by_owner_succeeds_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 3)),
        status=LeaveRequestStatus.PENDING,
    )
    service, requests, _balances, event_bus = _build(employee_ids={employee_id}, leave_types=[leave_type], requests=[pending])

    result = service.cancel_leave(
        CancelLeaveRequest(leave_request_id=pending.id, acting_employee_id=employee_id, cancellation_reason="Plans changed")
    )

    assert result.status == "cancelled"
    assert any(isinstance(e, LeaveRequestCancelled) for e in event_bus.published)


def test_cancel_leave_raises_ownership_error_for_different_employee() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.PENDING,
    )
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], requests=[pending])

    with pytest.raises(LeaveRequestOwnershipError):
        service.cancel_leave(CancelLeaveRequest(leave_request_id=pending.id, acting_employee_id=uuid.uuid4()))


def test_cancel_leave_raises_when_already_cancelled() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    cancelled = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.CANCELLED,
    )
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], requests=[cancelled])

    with pytest.raises(LeaveRequestNotCancellableError):
        service.cancel_leave(CancelLeaveRequest(leave_request_id=cancelled.id, acting_employee_id=employee_id))


def test_cancel_leave_of_approved_request_restores_balance() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    approved = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 3)),  # 3 days
        status=LeaveRequestStatus.APPROVED,
    )
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("20"), used_days=Decimal("3")
    )
    service, _requests, balances, _events = _build(
        employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[approved]
    )

    service.cancel_leave(CancelLeaveRequest(leave_request_id=approved.id, acting_employee_id=employee_id))

    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=year)
    assert updated.used_days == Decimal("0")


def test_cancel_leave_raises_not_found_for_unknown_request() -> None:
    service, *_ = _build()

    with pytest.raises(LeaveRequestNotFoundError):
        service.cancel_leave(CancelLeaveRequest(leave_request_id=uuid.uuid4(), acting_employee_id=uuid.uuid4()))


# --- approve / reject (Approval module extension point) ------------------


def test_approve_increases_used_days_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 4)),  # 4 days
        status=LeaveRequestStatus.PENDING,
    )
    balance = LeaveBalance(id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("20"))
    approver_id = uuid.uuid4()
    service, _requests, balances, event_bus = _build(
        employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[pending]
    )

    result = service.approve(ApproveLeaveRequest(leave_request_id=pending.id, approved_by=approver_id, comments="OK"))

    assert result.status == "approved"
    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=year)
    assert updated.used_days == Decimal("4")
    assert any(isinstance(e, LeaveRequestApproved) for e in event_bus.published)


def test_reject_does_not_change_balance_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 4)),
        status=LeaveRequestStatus.PENDING,
    )
    balance = LeaveBalance(id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("20"))
    service, _requests, balances, event_bus = _build(
        employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[pending]
    )

    result = service.reject(RejectLeaveRequest(leave_request_id=pending.id, comments="Insufficient coverage"))

    assert result.status == "rejected"
    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=year)
    assert updated.used_days == Decimal("0")
    assert any(isinstance(e, LeaveRequestRejected) for e in event_bus.published)


def test_get_by_id_enriched_raises_not_found_for_unknown_request() -> None:
    service, *_ = _build()

    with pytest.raises(LeaveRequestNotFoundError):
        service.get_by_id_enriched(uuid.uuid4())
