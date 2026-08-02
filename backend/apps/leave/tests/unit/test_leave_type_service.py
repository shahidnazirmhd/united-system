"""Unit tests for LeaveTypeService (Phase 13: Leave Type Management) —
hand-rolled fake repository, no Django."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from apps.leave.application.dtos import CreateLeaveTypeRequest, LeaveTypeListQuery, UpdateLeaveTypeRequest
from apps.leave.application.services.leave_type_service import LeaveTypeService
from apps.leave.domain.entities import LeaveType
from apps.leave.domain.exceptions import DuplicateLeaveTypeCodeError, LeaveTypeNotFoundError
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.repository import PageResult, QueryParams


class FakeUnitOfWork(UnitOfWork):
    def commit(self):
        pass

    def rollback(self):
        pass


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

    def list(self, query: QueryParams):
        items = list(self._leave_types)
        if "is_active" in query.filters:
            items = [lt for lt in items if lt.is_active == query.filters["is_active"]]
        return PageResult(items=items, total_count=len(items), page=query.page, page_size=query.page_size)

    def create(self, entity):
        self._leave_types.append(entity)
        return entity

    def update(self, entity):
        self._leave_types = [entity if lt.id == entity.id else lt for lt in self._leave_types]
        return entity

    def delete(self, entity_id):
        raise NotImplementedError


def _service(leave_types=None) -> LeaveTypeService:
    return LeaveTypeService(leave_type_repository=FakeLeaveTypeRepository(leave_types or []), unit_of_work=FakeUnitOfWork())


def test_create_leave_type_succeeds_with_a_unique_code() -> None:
    service = _service()

    result = service.create_leave_type(
        CreateLeaveTypeRequest(name="Sick Leave", code="SICK", default_annual_days=Decimal("10"))
    )

    assert result.code == "SICK"
    assert result.is_active is True


def test_create_leave_type_rejects_a_duplicate_code() -> None:
    existing = LeaveType(id=uuid.uuid4(), name="Annual Leave", code="ANNUAL")
    service = _service([existing])

    with pytest.raises(DuplicateLeaveTypeCodeError):
        service.create_leave_type(CreateLeaveTypeRequest(name="Another Annual", code="ANNUAL"))


def test_update_leave_type_raises_when_not_found() -> None:
    service = _service()

    with pytest.raises(LeaveTypeNotFoundError):
        service.update_leave_type(
            UpdateLeaveTypeRequest(
                leave_type_id=uuid.uuid4(),
                name="X",
                code="X",
                default_annual_days=Decimal("0"),
                is_paid=True,
                requires_approval=True,
            )
        )


def test_update_leave_type_can_reactivate_a_deactivated_row() -> None:
    existing = LeaveType(id=uuid.uuid4(), name="Annual Leave", code="ANNUAL", is_active=False)
    service = _service([existing])

    result = service.update_leave_type(
        UpdateLeaveTypeRequest(
            leave_type_id=existing.id,
            name="Annual Leave",
            code="ANNUAL",
            default_annual_days=Decimal("20"),
            is_paid=True,
            requires_approval=True,
            is_active=True,
        )
    )

    assert result.is_active is True


def test_update_leave_type_rejects_a_code_already_used_by_another_row() -> None:
    annual = LeaveType(id=uuid.uuid4(), name="Annual Leave", code="ANNUAL")
    sick = LeaveType(id=uuid.uuid4(), name="Sick Leave", code="SICK")
    service = _service([annual, sick])

    with pytest.raises(DuplicateLeaveTypeCodeError):
        service.update_leave_type(
            UpdateLeaveTypeRequest(
                leave_type_id=sick.id,
                name="Sick Leave",
                code="ANNUAL",
                default_annual_days=Decimal("10"),
                is_paid=True,
                requires_approval=True,
            )
        )


def test_list_all_includes_inactive_rows_unlike_list_active() -> None:
    active = LeaveType(id=uuid.uuid4(), name="Annual Leave", code="ANNUAL", is_active=True)
    inactive = LeaveType(id=uuid.uuid4(), name="Old Leave", code="OLD", is_active=False)
    service = _service([active, inactive])

    result = service.list_all(LeaveTypeListQuery())

    assert {lt.code for lt in result.items} == {"ANNUAL", "OLD"}
