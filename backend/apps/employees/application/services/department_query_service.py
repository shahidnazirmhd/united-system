"""Read side of Department (Phase 12: Department CRUD).

`parent_department_name`/`head_employee_name` are resolved only for
single-record reads (`get_by_id`), not `list` — identical N+1-avoidance
reasoning to `EmployeeQueryService`'s docstring: a generic
`DjangoBaseRepository.list()` has no select_related/prefetch path, so
resolving two extra names per row would cost up to two extra queries per
row of a page.
"""
from __future__ import annotations

import uuid

from apps.employees.application.dtos import DepartmentListQuery, DepartmentResponse
from apps.employees.application.mappers import department_to_response
from apps.employees.domain.entities import Department
from apps.employees.domain.exceptions import DepartmentNotFoundError
from apps.employees.domain.repositories import DepartmentRepository, EmployeeRepository
from shared_kernel.domain.repository import PageResult, QueryParams

_SEARCH_FIELDS = ("name", "code")
_DEFAULT_ORDERING = ("name",)


class DepartmentQueryService:
    def __init__(self, department_repository: DepartmentRepository, employee_repository: EmployeeRepository) -> None:
        self._departments = department_repository
        self._employees = employee_repository

    def get_by_id(self, department_id: uuid.UUID) -> DepartmentResponse:
        department = self._departments.get_by_id(department_id)
        if department is None:
            raise DepartmentNotFoundError()
        return self._to_enriched_response(department)

    def list(self, query: DepartmentListQuery) -> PageResult[DepartmentResponse]:
        filters: dict[str, object] = {}
        if query.is_active is not None:
            filters["is_active"] = query.is_active

        page_result = self._departments.list(
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
            items=[department_to_response(d) for d in page_result.items],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )

    def _to_enriched_response(self, department: Department) -> DepartmentResponse:
        parent_name = None
        if department.parent_department_id is not None:
            parent = self._departments.get_by_id(department.parent_department_id)
            if parent is not None:
                parent_name = parent.name

        head_name = None
        if department.head_employee_id is not None:
            head = self._employees.get_by_id(department.head_employee_id)
            if head is not None:
                head_name = head.profile.full_name

        return department_to_response(
            department, parent_department_name=parent_name, head_employee_name=head_name
        )
