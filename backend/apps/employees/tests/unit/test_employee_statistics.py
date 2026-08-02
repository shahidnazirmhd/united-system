"""Unit tests for `EmployeeQueryService.get_statistics` (Phase 14: Dashboard)
— hand-rolled fake repository, no Django, no database. A dedicated fake
repository (not the shared `FakeEmployeeRepository` in
test_employee_query_service.py) since this is the only test in this module
that needs `get_statistics_snapshot`.
"""
from __future__ import annotations

import uuid
from datetime import date

from apps.employees.application.services.employee_query_service import EmployeeQueryService
from apps.employees.domain.entities import Department
from apps.employees.domain.repositories import EmployeeStatisticsSnapshot


class FakeEmployeeStatisticsRepository:
    def __init__(self, snapshot: EmployeeStatisticsSnapshot):
        self._snapshot = snapshot

    def get_statistics_snapshot(self, *, new_hires_since: date) -> EmployeeStatisticsSnapshot:
        return self._snapshot

    # Unused by these tests, present to satisfy the interface shape.
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


class FakeDepartmentRepository:
    def __init__(self, departments: dict | None = None):
        self._departments = departments or {}

    def get_by_id(self, department_id):
        return self._departments.get(department_id)

    def get_by_ids(self, ids):
        return [department for dept_id, department in self._departments.items() if dept_id in ids]

    def exists(self, department_id):
        return department_id in self._departments


def test_get_statistics_computes_inactive_as_total_minus_active_minus_terminated() -> None:
    department_id = uuid.uuid4()
    snapshot = EmployeeStatisticsSnapshot(
        total=10,
        by_status={"active": 6, "terminated": 1},
        by_current_status={"working": 8, "on_leave": 2},
        by_employment_type={"full_time": 9, "contract": 1},
        by_department=[(department_id, 10)],
        new_hires_since=3,
    )
    service = EmployeeQueryService(
        FakeEmployeeStatisticsRepository(snapshot),
        FakeDepartmentRepository({department_id: Department(id=department_id, name="Engineering", code="ENG")}),
    )

    result = service.get_statistics()

    assert result.total_employees == 10
    assert result.active_count == 6
    assert result.terminated_count == 1
    # inactive = total(10) - active(6) - terminated(1) = 3 (ON_LEAVE + SUSPENDED)
    assert result.inactive_count == 3
    assert result.new_hires_this_month == 3
    assert result.status_breakdown == {"active": 6, "terminated": 1}
    assert result.current_status_breakdown == {"working": 8, "on_leave": 2}
    assert result.employment_type_breakdown == {"full_time": 9, "contract": 1}
    assert len(result.department_breakdown) == 1
    assert result.department_breakdown[0].department_name == "Engineering"
    assert result.department_breakdown[0].count == 10


def test_get_statistics_never_returns_a_negative_inactive_count() -> None:
    """Defensive: even if by_status somehow reports active+terminated >
    total (a data inconsistency this method has no way to actually produce
    in practice, since both come from the same table), inactive_count must
    floor at zero rather than go negative."""
    snapshot = EmployeeStatisticsSnapshot(total=1, by_status={"active": 1, "terminated": 1})
    service = EmployeeQueryService(FakeEmployeeStatisticsRepository(snapshot), FakeDepartmentRepository())

    result = service.get_statistics()

    assert result.inactive_count == 0


def test_get_statistics_labels_an_unresolved_department_as_unassigned() -> None:
    unknown_department_id = uuid.uuid4()
    snapshot = EmployeeStatisticsSnapshot(total=2, by_department=[(unknown_department_id, 2)])
    service = EmployeeQueryService(FakeEmployeeStatisticsRepository(snapshot), FakeDepartmentRepository())

    result = service.get_statistics()

    assert result.department_breakdown[0].department_name == "Unassigned"
