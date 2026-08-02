"""Facade composing Department's command and query services into the
single object the interface layer depends on
(`DepartmentViewSet.get_service()`), matching `EmployeeService`'s exact
precedent — and for the same reason: `BaseViewSet`'s generic `list()`/
`retrieve()` (`shared_kernel/api/base_viewset.py`) call
`get_service().list(query)`/`.get_by_id(pk)` expecting the *enriched*
`DepartmentResponse` shape back, not a raw `Department` entity, so this
facade's methods are hand-written delegations to the query service, never
inherited from `BaseService` directly on this class.
"""
from __future__ import annotations

import uuid

from apps.employees.application.dtos import (
    CreateDepartmentRequest,
    DepartmentListQuery,
    DepartmentResponse,
    UpdateDepartmentRequest,
)
from apps.employees.application.services.department_command_service import DepartmentCommandService
from apps.employees.application.services.department_query_service import DepartmentQueryService
from shared_kernel.domain.repository import PageResult, QueryParams


def _coerce_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes")


class DepartmentService:
    def __init__(self, command_service: DepartmentCommandService, query_service: DepartmentQueryService) -> None:
        self._commands = command_service
        self._queries = query_service

    # --- reads (delegate to DepartmentQueryService) ---------------------
    def get_by_id(self, department_id: uuid.UUID) -> DepartmentResponse:
        return self._queries.get_by_id(department_id)

    def list(self, query: DepartmentListQuery | QueryParams) -> PageResult[DepartmentResponse]:
        if isinstance(query, QueryParams):
            # Query-string values arrive as plain strings (see
            # shared_kernel/api/query_params.py) — coerced here the same
            # way EmployeeService.list() coerces department_id to a UUID.
            return self._queries.list(
                DepartmentListQuery(
                    is_active=_coerce_bool(query.filters.get("is_active")),
                    search=query.search,
                    ordering=query.ordering,
                    page=query.page,
                    page_size=query.page_size,
                )
            )
        return self._queries.list(query)

    # --- writes (delegate to DepartmentCommandService) ------------------
    def create_department(self, request: CreateDepartmentRequest) -> DepartmentResponse:
        return self._commands.create_department(request)

    def update_department(self, request: UpdateDepartmentRequest) -> DepartmentResponse:
        return self._commands.update_department(request)
