"""Read side of the Employee module: get, list, search, and (Phase 7) the
caller's own profile.

"List" and "search" (two separate endpoints in the brief, EMPLOYEE_API.md)
collapse to the same underlying mechanism here — a plain list omits
`search`, a search request sets it — rather than maintaining two parallel
query code paths for what is, underneath, one repository call with an
optional extra filter. See shared_kernel/domain/repository.py:QueryParams.

`manager_name` is resolved only for single-record reads (`get_by_id`,
`get_my_profile`), not `list`/`search` — resolving it for every row of a
list would mean an extra query per row (no select_related/prefetch path
exists in the generic `DjangoBaseRepository.list()`, and `manager_id` is a
self-referential FK with no cheap batch lookup already on hand), which is a
real N+1 cost for a feature (a Telegram profile card, or the Employee
Detail page) that only ever needs a single record at a time. List/search
responses leave `manager_name` `None`; the Telegram formatter (or any other
consumer) treats that the same as any other "unavailable" field.

`department_name` **is** resolved for `list`/`search` too (bugfix — the
Employee List table's Department column was always showing "—" even for
employees with a department, because this field used to follow the same
single-record-only rule as `manager_name` above). Unlike `manager_id`,
`department_id` has a cheap batch lookup available
(`DepartmentRepository.get_by_ids`), so `list()` below does exactly one
extra query per page — for every *distinct* department on that page, not
one query per employee row — instead of skipping the resolution outright.
"""
from __future__ import annotations

import uuid
from datetime import date

from apps.employees.application.dtos import (
    EmployeeDepartmentStat,
    EmployeeListQuery,
    EmployeeResponse,
    EmployeeStatisticsResponse,
)
from apps.employees.application.mappers import employee_to_response
from apps.employees.application.ports import UserLookupPort
from apps.employees.domain.entities import Employee
from apps.employees.domain.enums import EmployeeStatus
from apps.employees.domain.exceptions import EmployeeNotFoundError, EmployeeNotLinkedToTelegramError
from apps.employees.domain.repositories import DepartmentRepository, EmployeeRepository
from shared_kernel.domain.repository import PageResult, QueryParams

_SEARCH_FIELDS = ("first_name", "last_name", "employee_code", "work_email")
_DEFAULT_ORDERING = ("employee_code",)


class EmployeeQueryService:
    def __init__(
        self,
        employee_repository: EmployeeRepository,
        department_repository: DepartmentRepository,
        user_lookup: UserLookupPort | None = None,
    ) -> None:
        self._employees = employee_repository
        self._departments = department_repository
        # Optional (default None), same backward-compatibility reasoning as
        # EmployeeCommandService's own user_lookup param — only the
        # linked_user_email enrichment (Phase 12 bugfix) needs this.
        self._user_lookup = user_lookup

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

        linked_user_email = None
        if employee.user_id is not None and self._user_lookup is not None:
            linked_user_email = self._user_lookup.get_user_email(employee.user_id)

        return employee_to_response(
            employee,
            department_name=department_name,
            manager_name=manager_name,
            linked_user_email=linked_user_email,
        )

    def list_employee_ids_by_current_status(self, statuses: list[str]) -> list[uuid.UUID]:
        """Round 14 items 6/8 — batch lookup for
        `apps.leave`'s daily status-reconciliation task (via
        `EmployeeLookupPort.list_employee_ids_on_leave_status`): every
        employee currently in one of `statuses`
        (`current_status__in=...`). Not paginated — this is an internal
        batch read for another module's background job, not a user-facing
        list, so `page_size` is set high enough to cover any realistic
        headcount in one query rather than looping pages."""
        page_result = self._employees.list(
            QueryParams(filters={"current_status__in": statuses}, page_size=100_000)
        )
        return [e.id for e in page_result.items]

    # --- Statistics (Phase 14: Dashboard) --------------------------------
    def get_statistics(self) -> EmployeeStatisticsResponse:
        """Aggregate counts for the Dashboard's Employee Statistics widgets
        — consumed through `apps.dashboard`'s own `EmployeeStatisticsPort`
        adapter, never by that module querying `EmployeeRecord` directly
        (see that adapter's docstring). `inactive_count` is deliberately
        `total - active - terminated` (i.e. `ON_LEAVE` + `SUSPENDED`) rather
        than a fourth named bucket — the Dashboard's own KPI cards only ever
        distinguish "active," "inactive-but-not-terminated," and
        "terminated"; the full per-status breakdown is still available via
        `status_breakdown` for anything that wants finer detail (e.g. a
        chart)."""
        since = date.today().replace(day=1)
        snapshot = self._employees.get_statistics_snapshot(new_hires_since=since)

        active = snapshot.by_status.get(EmployeeStatus.ACTIVE.value, 0)
        terminated = snapshot.by_status.get(EmployeeStatus.TERMINATED.value, 0)
        inactive = max(0, snapshot.total - active - terminated)

        department_ids = frozenset(dept_id for dept_id, _count in snapshot.by_department)
        department_names = {d.id: d.name for d in self._departments.get_by_ids(department_ids)}
        department_breakdown = [
            EmployeeDepartmentStat(
                department_id=dept_id,
                department_name=department_names.get(dept_id, "Unassigned"),
                count=count,
            )
            for dept_id, count in snapshot.by_department
        ]

        return EmployeeStatisticsResponse(
            total_employees=snapshot.total,
            active_count=active,
            inactive_count=inactive,
            terminated_count=terminated,
            status_breakdown=snapshot.by_status,
            current_status_breakdown=snapshot.by_current_status,
            employment_type_breakdown=snapshot.by_employment_type,
            department_breakdown=department_breakdown,
            new_hires_this_month=snapshot.new_hires_since,
        )

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

        # One batch query for every distinct department on this page — see
        # this module's docstring on why department_name (unlike
        # manager_name) is resolved for list/search, not left None.
        department_ids = frozenset(e.employment_info.department_id for e in page_result.items)
        department_names = {d.id: d.name for d in self._departments.get_by_ids(department_ids)}

        return PageResult(
            items=[
                employee_to_response(
                    e, department_name=department_names.get(e.employment_info.department_id)
                )
                for e in page_result.items
            ],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )
