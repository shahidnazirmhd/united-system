"""Unit tests for LeaveBalanceService — hand-rolled fakes, no Django."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from apps.leave.application.dtos import AdjustLeaveBalanceRequest
from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.domain.entities import LeaveBalance, LeaveRequest, LeaveType
from apps.leave.domain.enums import LeaveBalanceAdjustmentType, LeaveRequestStatus
from apps.leave.domain.exceptions import (
    InvalidLeaveBalanceAdjustmentError,
    LeaveEmployeeNotFoundError,
    LeaveTypeNotFoundError,
)
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.value_objects import DateRange


class FakeUnitOfWork(UnitOfWork):
    def commit(self):
        pass

    def rollback(self):
        pass


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


class FakeLeaveTypeRepository:
    def __init__(self, leave_types: list[LeaveType] | None = None):
        self._leave_types = list(leave_types or [])

    def get_by_id(self, leave_type_id):
        return next((lt for lt in self._leave_types if lt.id == leave_type_id), None)

    def get_by_code(self, code):
        return next((lt for lt in self._leave_types if lt.code == code), None)

    def list_active(self):
        return [lt for lt in self._leave_types if lt.is_active]

    def exists(self, leave_type_id):
        return any(lt.id == leave_type_id and lt.is_active for lt in self._leave_types)


class FakeLeaveRequestRepository:
    def __init__(self, requests: list[LeaveRequest] | None = None):
        self._requests = list(requests or [])

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

    def get_overlapping_for_employee(self, **kwargs):
        raise NotImplementedError

    def get_duplicate(self, **kwargs):
        raise NotImplementedError

    def get_by_id(self, entity_id):
        raise NotImplementedError

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


class FakeEmployeeLookupPort:
    def __init__(self, known_employee_ids: set[uuid.UUID] | None = None):
        self._known = known_employee_ids or set()

    def employee_exists(self, employee_id):
        return employee_id in self._known

    def get_employee_id_by_user_id(self, user_id):
        raise NotImplementedError

    def get_employee_id_by_telegram_user_id(self, telegram_user_id):
        raise NotImplementedError

    def get_manager_employee_id(self, employee_id):
        raise NotImplementedError

    def is_employee_linked_to_telegram(self, employee_id):
        raise NotImplementedError


class FakeLeaveBalanceAdjustmentRepository:
    def __init__(self):
        self.created: list = []

    def create(self, adjustment, *, created_by):
        self.created.append((adjustment, created_by))
        return adjustment

    def list_by_employee(self, *, employee_id, leave_type_id=None, year=None):
        return [a for a, _ in self.created if a.employee_id == employee_id]


def _leave_type(**overrides) -> LeaveType:
    return LeaveType(
        id=overrides.pop("id", uuid.uuid4()),
        name=overrides.pop("name", "Annual Leave"),
        code=overrides.pop("code", "ANNUAL"),
        default_annual_days=overrides.pop("default_annual_days", Decimal("20")),
        is_active=overrides.pop("is_active", True),
    )


def _service(balances=None, leave_types=None, requests=None) -> LeaveBalanceService:
    return LeaveBalanceService(
        leave_balance_repository=FakeLeaveBalanceRepository(balances or []),
        leave_type_repository=FakeLeaveTypeRepository(leave_types or []),
        leave_request_repository=FakeLeaveRequestRepository(requests or []),
        unit_of_work=FakeUnitOfWork(),
    )


def test_get_balance_returns_zeroed_response_when_no_row_exists() -> None:
    leave_type = _leave_type()
    service = _service(leave_types=[leave_type])
    employee_id = uuid.uuid4()

    result = service.get_balance(employee_id=employee_id, leave_type_id=leave_type.id, year=2026)

    assert result.entitled_days == Decimal("0")
    assert result.available_days == Decimal("0")
    assert result.leave_type_name == "Annual Leave"


def test_get_balance_returns_existing_row() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        year=2026,
        entitled_days=Decimal("20"),
        used_days=Decimal("5"),
    )
    service = _service(balances=[balance], leave_types=[leave_type])

    result = service.get_balance(employee_id=employee_id, leave_type_id=leave_type.id, year=2026)

    assert result.available_days == Decimal("15")


def test_list_balances_includes_every_active_leave_type_even_without_a_row() -> None:
    employee_id = uuid.uuid4()
    annual = _leave_type(name="Annual Leave", code="ANNUAL")
    sick = _leave_type(name="Sick Leave", code="SICK")
    only_annual_balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=annual.id, year=2026, entitled_days=Decimal("20")
    )
    service = _service(balances=[only_annual_balance], leave_types=[annual, sick])

    result = service.list_balances(employee_id=employee_id, year=2026)

    assert {r.leave_type_name for r in result} == {"Annual Leave", "Sick Leave"}
    sick_result = next(r for r in result if r.leave_type_name == "Sick Leave")
    assert sick_result.entitled_days == Decimal("0")


def test_provision_initial_balance_creates_row_from_default_annual_days() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type(default_annual_days=Decimal("15"))
    balances = FakeLeaveBalanceRepository()
    service = LeaveBalanceService(
        leave_balance_repository=balances,
        leave_type_repository=FakeLeaveTypeRepository([leave_type]),
        leave_request_repository=FakeLeaveRequestRepository(),
        unit_of_work=FakeUnitOfWork(),
    )

    service.provision_initial_balance(employee_id=employee_id, leave_type=leave_type, year=2026)

    created = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=2026)
    assert created is not None
    assert created.entitled_days == Decimal("15")


def test_provision_initial_balance_is_idempotent() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balances = FakeLeaveBalanceRepository()
    service = LeaveBalanceService(
        leave_balance_repository=balances,
        leave_type_repository=FakeLeaveTypeRepository([leave_type]),
        leave_request_repository=FakeLeaveRequestRepository(),
        unit_of_work=FakeUnitOfWork(),
    )

    service.provision_initial_balance(employee_id=employee_id, leave_type=leave_type, year=2026)
    service.provision_initial_balance(employee_id=employee_id, leave_type=leave_type, year=2026)

    assert len(balances.list_by_employee(employee_id=employee_id, year=2026)) == 1


def test_increase_used_days_updates_existing_balance() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=2026, entitled_days=Decimal("20")
    )
    balances = FakeLeaveBalanceRepository([balance])
    service = LeaveBalanceService(
        leave_balance_repository=balances,
        leave_type_repository=FakeLeaveTypeRepository([leave_type]),
        leave_request_repository=FakeLeaveRequestRepository(),
        unit_of_work=FakeUnitOfWork(),
    )

    service.increase_used_days(employee_id=employee_id, leave_type_id=leave_type.id, year=2026, amount=Decimal("4"))

    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=2026)
    assert updated.used_days == Decimal("4")


def test_decrease_used_days_restores_balance_on_cancel_of_approved() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        year=2026,
        entitled_days=Decimal("20"),
        used_days=Decimal("5"),
    )
    balances = FakeLeaveBalanceRepository([balance])
    service = LeaveBalanceService(
        leave_balance_repository=balances,
        leave_type_repository=FakeLeaveTypeRepository([leave_type]),
        leave_request_repository=FakeLeaveRequestRepository(),
        unit_of_work=FakeUnitOfWork(),
    )

    service.decrease_used_days(employee_id=employee_id, leave_type_id=leave_type.id, year=2026, amount=Decimal("5"))

    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=2026)
    assert updated.used_days == Decimal("0")


# --- adjust_balance (Phase 13: Leave Balance Adjustment / Opening) --------


def _adjustment_service(*, balances=None, leave_types, known_employee_ids, adjustments=None):
    return (
        LeaveBalanceService(
            leave_balance_repository=FakeLeaveBalanceRepository(balances or []),
            leave_type_repository=FakeLeaveTypeRepository(leave_types),
            leave_request_repository=FakeLeaveRequestRepository(),
            unit_of_work=FakeUnitOfWork(),
            employee_lookup=FakeEmployeeLookupPort(known_employee_ids),
            balance_adjustment_repository=adjustments,
        ),
        adjustments,
    )


def test_adjust_balance_opens_a_new_row_when_none_exists() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    adjustments = FakeLeaveBalanceAdjustmentRepository()
    service, _ = _adjustment_service(
        leave_types=[leave_type], known_employee_ids={employee_id}, adjustments=adjustments
    )

    result = service.adjust_balance(
        AdjustLeaveBalanceRequest(
            employee_id=employee_id,
            leave_type_id=leave_type.id,
            year=2026,
            entitled_days=Decimal("18"),
            used_days=Decimal("0"),
            carried_forward_days=Decimal("2"),
            reason="New year opening entitlement",
            adjusted_by=uuid.uuid4(),
        )
    )

    assert result.adjustment_type == LeaveBalanceAdjustmentType.OPENING.value
    assert result.previous_entitled_days == Decimal("0")
    assert result.new_entitled_days == Decimal("18")
    assert len(adjustments.created) == 1


def test_adjust_balance_updates_an_existing_row_and_records_previous_values() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    existing = LeaveBalance(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        year=2026,
        entitled_days=Decimal("20"),
        used_days=Decimal("5"),
        carried_forward_days=Decimal("0"),
    )
    adjustments = FakeLeaveBalanceAdjustmentRepository()
    service, _ = _adjustment_service(
        balances=[existing], leave_types=[leave_type], known_employee_ids={employee_id}, adjustments=adjustments
    )

    result = service.adjust_balance(
        AdjustLeaveBalanceRequest(
            employee_id=employee_id,
            leave_type_id=leave_type.id,
            year=2026,
            entitled_days=Decimal("25"),
            used_days=Decimal("5"),
            carried_forward_days=Decimal("0"),
            reason="Correcting a data-entry error",
            adjusted_by=uuid.uuid4(),
        )
    )

    assert result.adjustment_type == LeaveBalanceAdjustmentType.ADJUSTMENT.value
    assert result.previous_entitled_days == Decimal("20")
    assert result.new_entitled_days == Decimal("25")


def test_adjust_balance_rejects_a_negative_value() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    service, _ = _adjustment_service(leave_types=[leave_type], known_employee_ids={employee_id})

    with pytest.raises(InvalidLeaveBalanceAdjustmentError):
        service.adjust_balance(
            AdjustLeaveBalanceRequest(
                employee_id=employee_id,
                leave_type_id=leave_type.id,
                year=2026,
                entitled_days=Decimal("-1"),
                used_days=Decimal("0"),
                carried_forward_days=Decimal("0"),
                reason="Invalid",
                adjusted_by=None,
            )
        )


def test_adjust_balance_rejects_an_unknown_employee() -> None:
    leave_type = _leave_type()
    service, _ = _adjustment_service(leave_types=[leave_type], known_employee_ids=set())

    with pytest.raises(LeaveEmployeeNotFoundError):
        service.adjust_balance(
            AdjustLeaveBalanceRequest(
                employee_id=uuid.uuid4(),
                leave_type_id=leave_type.id,
                year=2026,
                entitled_days=Decimal("10"),
                used_days=Decimal("0"),
                carried_forward_days=Decimal("0"),
                reason="Test",
                adjusted_by=None,
            )
        )


def test_adjust_balance_rejects_an_unknown_leave_type() -> None:
    employee_id = uuid.uuid4()
    service, _ = _adjustment_service(leave_types=[], known_employee_ids={employee_id})

    with pytest.raises(LeaveTypeNotFoundError):
        service.adjust_balance(
            AdjustLeaveBalanceRequest(
                employee_id=employee_id,
                leave_type_id=uuid.uuid4(),
                year=2026,
                entitled_days=Decimal("10"),
                used_days=Decimal("0"),
                carried_forward_days=Decimal("0"),
                reason="Test",
                adjusted_by=None,
            )
        )
