"""Read side of the Employee module: get, list, search, and (Phase 7) the
caller's own profile.

"List" and "search" (two separate endpoints in the brief, EMPLOYEE_API.md)
collapse to the same underlying mechanism here — a plain list omits
`search`, a search request sets it — rather than maintaining two parallel
query code paths for what is, underneath, one repository call with an
optional extra filter. See shared_kernel/domain/repository.py:QueryParams.

`department_name`/`manager_name` are resolved only for single-record reads
(`get_by_id`, `get_my_profile`), not `list`/`search` — resolving them for
every row of a list would mean up to two extra queries per row (no
select_related/prefetch path exists in the generic
`DjangoBaseRepository.list()`), which is a real N+1 cost for a feature
(a Telegram profile card) that only ever needs a single record at a time.
List/search responses leave these fields `None`; the Telegram formatter (or
any other consumer) treats that the same as any other "unavailable" field.
"""
from __future__ import annotations

import uuid

from apps.employees.application.dtos import EmployeeListQuery, EmployeeResponse
from apps.employees.application.mappers import employee_to_response
from apps.employees.domain.entities import Employee
from apps.employees.domain.exceptions import EmployeeNotFoundError, EmployeeNotLinkedToTelegramError
from apps.employees.domain.repositories import DepartmentRepository, EmployeeRepository
from shared_kernel.domain.repository import PageResult, QueryParams

_SEARCH_FIELDS = ("first_name", "last_name", "employee_code", "work_email")
_DEFAULT_ORDERING = ("employee_code",)


class EmployeeQueryService:
    def __init__(self, employee_repository: EmployeeRepository, department_repository: DepartmentRepository) -> None:
        self._employees = employee_repository
        self._departments = department_repository

    def get_by_id(self, employee_id: uuid.UUID) -> EmployeeResponse:
        employee = self._employees.get_by_id(employee_id)
        if employee is None:
            raise EmployeeNotFoundError()
        return self._to_enriched_response(employee)

    def get_my_profile(self, user_id: uuid.UUID) -> EmployeeResponse:
        """Phase 7 self-service: the employee record linked to the caller's
        own User account — no employees.view_employees permission required,
        mirroring GET /api/v1/auth/me/'s "own data needs no elevated
        permission" precedent exactly."""
        employee = self._employees.get_by_user_id(user_id)
        if employee is None:
            raise EmployeeNotFoundError()
        return self._to_enriched_response(employee)

    def get_profile_by_telegram_user_id(self, telegram_user_id: int) -> EmployeeResponse:
        """Employee & Telegram Authentication refactor: the read every
        Gateway-facing "my profile"/"employment status" call resolves
        through (see interface/views.py's EmployeeTelegramProfileView) —
        `telegram_user_id` is, per the refactor's own spec, "the only
        information required to identify the employee in future Telegram
        requests," so this is the one method that turns that id into a
        full profile. Distinct exception from get_my_profile's
        EmployeeNotFoundError: "no employee has this Telegram id linked"
        is a link-state question, not a record-existence question — see
        EmployeeNotLinkedToTelegramError's docstring.
        """
        employee = self._employees.get_by_telegram_user_id(telegram_user_id)
        if employee is None:
            raise EmployeeNotLinkedToTelegramError()
        return self._to_enriched_response(employee)

    def _to_enriched_response(self, employee: Employee) -> EmployeeResponse:
        department_name = None
        department = self._departments.get_by_id(employee.employment_info.department_id)
        if department is not None:
            department_name = department.name

        manager_name = None
        if employee.employment_info.manager_id is not None:
            manager = self._employees.get_by_id(employee.employment_info.manager_id)
            if manager is not None:
                manager_name = manager.profile.full_name

        return employee_to_response(employee, department_name=department_name, manager_name=manager_name)

    def list(self, query: EmployeeListQuery) -> PageResult[EmployeeResponse]:
        filters: dict[str, object] = {}
        if query.department_id is not None:
            filters["department_id"] = query.department_id
        if query.status is not None:
            filters["employment_status"] = query.status
        if query.employment_type is not None:
            filters["employment_type"] = query.employment_type

        page_result = self._employees.list(
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
            items=[employee_to_response(e) for e in page_result.items],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )
