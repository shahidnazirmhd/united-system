"""Facade composing the command and query services into the single object
the interface layer depends on (`EmployeeViewSet.get_service()` — see
interface/viewsets.py).

Delegation only, no logic of its own — its entire purpose is so a ViewSet
holds one dependency instead of two. Concretely realizes all three names
the brief listed under "Services" (Employee Service / Employee Query
Service / Employee Command Service): the latter two are real, separately
testable classes; this is the thin composition of both.
"""
from __future__ import annotations

import uuid

from apps.employees.application.dtos import (
    CreateEmployeeRequest,
    EmployeeListQuery,
    EmployeeResponse,
    LinkUserToEmployeeRequest,
    UpdateEmployeeCurrentStatusRequest,
    UpdateEmployeeRequest,
)
from apps.employees.application.services.employee_command_service import EmployeeCommandService
from apps.employees.application.services.employee_query_service import EmployeeQueryService
from shared_kernel.domain.repository import PageResult, QueryParams


class EmployeeService:
    def __init__(self, command_service: EmployeeCommandService, query_service: EmployeeQueryService) -> None:
        self._commands = command_service
        self._queries = query_service

    # --- reads (delegate to EmployeeQueryService) -----------------------
    def get_by_id(self, employee_id: uuid.UUID) -> EmployeeResponse:
        return self._queries.get_by_id(employee_id)

    def get_my_profile(self, user_id: uuid.UUID) -> EmployeeResponse:
        return self._queries.get_my_profile(user_id)

    def get_profile_by_telegram_user_id(self, telegram_user_id: int) -> EmployeeResponse:
        return self._queries.get_profile_by_telegram_user_id(telegram_user_id)

    def list_employee_ids_by_current_status(self, statuses: list[str]) -> list[uuid.UUID]:
        return self._queries.list_employee_ids_by_current_status(statuses)

    def list(self, query: EmployeeListQuery | QueryParams) -> PageResult[EmployeeResponse]:
        # BaseViewSet.list() (shared_kernel/api/base_viewset.py) builds a
        # generic QueryParams from the request; EmployeeViewSet passes it
        # straight through here rather than translating to
        # EmployeeListQuery, so both shapes are accepted transparently.
        if isinstance(query, QueryParams):
            # Query-string values arrive as plain strings
            # (shared_kernel/api/query_params.py never parses UUIDs — it
            # doesn't know which filter keys are UUID-typed for an
            # arbitrary future module). Coerced here, the one place that
            # does know, so EmployeeListQuery.department_id stays a real
            # uuid.UUID rather than silently accepting a string that only
            # happens to work because Django's ORM is lenient about it.
            raw_department_id = query.filters.get("department_id")
            return self._queries.list(
                EmployeeListQuery(
                    department_id=uuid.UUID(str(raw_department_id)) if raw_department_id else None,
                    status=query.filters.get("employment_status"),
                    employment_type=query.filters.get("employment_type"),
                    search=query.search,
                    ordering=query.ordering,
                    page=query.page,
                    page_size=query.page_size,
                )
            )
        return self._queries.list(query)

    # --- writes (delegate to EmployeeCommandService) --------------------
    def create_employee(self, request: CreateEmployeeRequest) -> EmployeeResponse:
        return self._commands.create_employee(request)

    def update_employee(self, request: UpdateEmployeeRequest) -> EmployeeResponse:
        return self._commands.update_employee(request)

    def activate_employee(self, employee_id: uuid.UUID) -> EmployeeResponse:
        return self._commands.activate_employee(employee_id)

    def link_user(self, request: LinkUserToEmployeeRequest) -> EmployeeResponse:
        return self._commands.link_user(request)

    def deactivate_employee(self, employee_id: uuid.UUID) -> EmployeeResponse:
        return self._commands.deactivate_employee(employee_id)

    def update_current_status(self, request: UpdateEmployeeCurrentStatusRequest) -> EmployeeResponse:
        return self._commands.update_current_status(request)

    def enter_leave_status(self, employee_id: uuid.UUID, leave_status: str) -> EmployeeResponse:
        return self._commands.enter_leave_status(employee_id, leave_status)

    def exit_leave_status(self, employee_id: uuid.UUID) -> EmployeeResponse:
        return self._commands.exit_leave_status(employee_id)
