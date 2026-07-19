"""Unit tests for EmployeeQueryService — hand-rolled fake repository, no
Django, no database."""
from __future__ import annotations

import uuid
from datetime import date

import pytest

from apps.employees.application.dtos import EmployeeListQuery
from apps.employees.application.services.employee_query_service import EmployeeQueryService
from apps.employees.domain.entities import Employee
from apps.employees.domain.enums import EmploymentType
from apps.employees.domain.exceptions import EmployeeNotFoundError
from apps.employees.domain.value_objects import ContactInformation, EmployeeProfile, EmploymentInformation
from shared_kernel.domain.repository import PageResult
from shared_kernel.domain.value_objects import Email


def _employee(first_name: str, work_email: str) -> Employee:
    return Employee(
        id=uuid.uuid4(),
        employee_code=f"EMP-{first_name.upper()}",
        profile=EmployeeProfile(first_name=first_name, last_name="Test"),
        contact_info=ContactInformation(work_email=Email(work_email)),
        employment_info=EmploymentInformation(
            department_id=uuid.uuid4(),
            job_title="Engineer",
            employment_type=EmploymentType.FULL_TIME,
            date_of_joining=date(2024, 1, 1),
        ),
    )


class FakeEmployeeRepository:
    def __init__(self, employees: list[Employee]):
        self._employees = {e.id: e for e in employees}
        self.last_query = None

    def get_by_id(self, entity_id):
        return self._employees.get(entity_id)

    def list(self, query):
        self.last_query = query
        items = list(self._employees.values())
        return PageResult(items=items, total_count=len(items), page=query.page, page_size=query.page_size)

    # Unused by these tests, present to satisfy the interface shape.
    def get_by_employee_code(self, employee_code):
        raise NotImplementedError

    def get_by_work_email(self, work_email):
        raise NotImplementedError

    def get_by_user_id(self, user_id):
        raise NotImplementedError

    def exists_with_employee_code(self, employee_code):
        raise NotImplementedError

    def exists_with_work_email(self, work_email):
        raise NotImplementedError

    def next_employee_code(self):
        raise NotImplementedError

    def create(self, entity):
        raise NotImplementedError

    def update(self, entity):
        raise NotImplementedError

    def delete(self, entity_id):
        raise NotImplementedError

    def exists(self, entity_id):
        raise NotImplementedError


class FakeDepartmentRepository:
    """EmployeeQueryService enriches every single-record read with a
    department name (see _to_enriched_response) — this fake stands in for
    that lookup. An empty fake (no departments registered) is enough for
    tests that don't assert on department_name: _to_enriched_response
    already treats "not found" as None, not an error.
    """

    def __init__(self, departments: dict | None = None):
        self._departments = departments or {}

    def get_by_id(self, department_id):
        return self._departments.get(department_id)

    def exists(self, department_id):
        return department_id in self._departments


def test_get_by_id_raises_when_not_found() -> None:
    service = EmployeeQueryService(FakeEmployeeRepository([]), FakeDepartmentRepository())

    with pytest.raises(EmployeeNotFoundError):
        service.get_by_id(uuid.uuid4())


def test_get_by_id_returns_mapped_response() -> None:
    employee = _employee("Ada", "ada@example.com")
    service = EmployeeQueryService(FakeEmployeeRepository([employee]), FakeDepartmentRepository())

    result = service.get_by_id(employee.id)

    assert result.full_name == "Ada Test"
    assert result.work_email == "ada@example.com"


def test_list_builds_filters_from_query() -> None:
    repository = FakeEmployeeRepository([_employee("Ada", "ada@example.com")])
    service = EmployeeQueryService(repository, FakeDepartmentRepository())
    department_id = uuid.uuid4()

    service.list(EmployeeListQuery(department_id=department_id, status="active", search="ada"))

    assert repository.last_query.filters == {"department_id": department_id, "employment_status": "active"}
    assert repository.last_query.search == "ada"
    assert repository.last_query.search_fields == ("first_name", "last_name", "employee_code", "work_email")
