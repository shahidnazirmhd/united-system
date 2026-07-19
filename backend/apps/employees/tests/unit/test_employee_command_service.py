"""Unit tests for EmployeeCommandService — every dependency is a hand-rolled
fake, no Django, no database. Same discipline as
apps/identity/tests/unit/test_login_user_use_case.py.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from apps.employees.application.dtos import CreateEmployeeRequest
from apps.employees.application.services.employee_command_service import EmployeeCommandService
from apps.employees.domain.entities import Employee
from apps.employees.domain.enums import EmployeeStatus, EmploymentType
from apps.employees.domain.exceptions import (
    DepartmentNotFoundError,
    DuplicateWorkEmailError,
    InvalidEmployeeStatusTransitionError,
)
from apps.employees.domain.value_objects import ContactInformation, EmployeeProfile, EmploymentInformation
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.value_objects import Email


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


class FakeEmployeeRepository:
    def __init__(self, employees: list[Employee] | None = None):
        self._employees = {e.id: e for e in (employees or [])}
        self._code_counter = 1

    def get_by_id(self, entity_id):
        return self._employees.get(entity_id)

    def get_by_employee_code(self, employee_code):
        return next((e for e in self._employees.values() if e.employee_code == employee_code), None)

    def get_by_work_email(self, work_email):
        return next(
            (e for e in self._employees.values() if str(e.contact_info.work_email) == str(work_email)), None
        )

    def get_by_user_id(self, user_id):
        return next((e for e in self._employees.values() if e.user_id == user_id), None)

    def exists_with_employee_code(self, employee_code):
        return self.get_by_employee_code(employee_code) is not None

    def exists_with_work_email(self, work_email):
        return self.get_by_work_email(work_email) is not None

    def next_employee_code(self):
        code = f"EMP-{self._code_counter:06d}"
        self._code_counter += 1
        return code

    def list(self, query):
        raise NotImplementedError("not exercised by these tests")

    def create(self, entity):
        self._employees[entity.id] = entity
        return entity

    def update(self, entity):
        self._employees[entity.id] = entity
        return entity

    def delete(self, entity_id):
        self._employees.pop(entity_id, None)

    def exists(self, entity_id):
        return entity_id in self._employees


class FakeDepartmentRepository:
    def __init__(self, existing_ids: list[uuid.UUID] | None = None):
        self._ids = set(existing_ids or [])

    def get_by_id(self, department_id):
        return None

    def exists(self, department_id):
        return department_id in self._ids


def _create_request(department_id: uuid.UUID, **overrides) -> CreateEmployeeRequest:
    defaults = dict(
        first_name="Ada",
        last_name="Lovelace",
        work_email="ada@example.com",
        department_id=department_id,
        job_title="Software Engineer",
        employment_type="full_time",
        date_of_joining=date(2024, 1, 15),
    )
    defaults.update(overrides)
    return CreateEmployeeRequest(**defaults)


def _existing_employee(**overrides) -> Employee:
    department_id = overrides.pop("department_id", uuid.uuid4())
    status = overrides.pop("status", EmployeeStatus.ACTIVE)
    return Employee(
        id=overrides.pop("id", uuid.uuid4()),
        employee_code=overrides.pop("employee_code", "EMP-000001"),
        user_id=overrides.pop("user_id", None),
        profile=EmployeeProfile(first_name="Grace", last_name="Hopper"),
        contact_info=ContactInformation(work_email=Email(overrides.pop("work_email", "grace@example.com"))),
        employment_info=EmploymentInformation(
            department_id=department_id,
            job_title="Rear Admiral",
            employment_type=EmploymentType.FULL_TIME,
            date_of_joining=date(2000, 1, 1),
        ),
        status=status,
    )


def test_create_employee_succeeds() -> None:
    department_id = uuid.uuid4()
    service = EmployeeCommandService(
        employee_repository=FakeEmployeeRepository(),
        department_repository=FakeDepartmentRepository([department_id]),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    result = service.create_employee(_create_request(department_id))

    assert result.employee_code == "EMP-000001"
    assert result.status == "active"
    assert result.full_name == "Ada Lovelace"


def test_create_employee_raises_when_department_missing() -> None:
    service = EmployeeCommandService(
        employee_repository=FakeEmployeeRepository(),
        department_repository=FakeDepartmentRepository([]),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(DepartmentNotFoundError):
        service.create_employee(_create_request(uuid.uuid4()))


def test_create_employee_raises_on_duplicate_work_email() -> None:
    department_id = uuid.uuid4()
    existing = _existing_employee(department_id=department_id, work_email="ada@example.com")
    service = EmployeeCommandService(
        employee_repository=FakeEmployeeRepository([existing]),
        department_repository=FakeDepartmentRepository([department_id]),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(DuplicateWorkEmailError):
        service.create_employee(_create_request(department_id, work_email="ada@example.com"))


def test_deactivate_transitions_active_to_suspended() -> None:
    employee = _existing_employee(status=EmployeeStatus.ACTIVE)
    service = EmployeeCommandService(
        employee_repository=FakeEmployeeRepository([employee]),
        department_repository=FakeDepartmentRepository([employee.employment_info.department_id]),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    result = service.deactivate_employee(employee.id)

    assert result.status == "suspended"


def test_activate_raises_for_terminated_employee() -> None:
    employee = _existing_employee(status=EmployeeStatus.TERMINATED)
    service = EmployeeCommandService(
        employee_repository=FakeEmployeeRepository([employee]),
        department_repository=FakeDepartmentRepository([employee.employment_info.department_id]),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(InvalidEmployeeStatusTransitionError):
        service.activate_employee(employee.id)
