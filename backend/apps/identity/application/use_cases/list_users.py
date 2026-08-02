"""Lists users with pagination/filter/search — backs GET /auth/users/.

Mirrors `apps.employees.application.services.employee_query_service`'s
list() shape (filters dict, search+search_fields, ordering, pagination)
even though Identity keeps its own one-class-per-use-case style rather
than Employee's BaseService — the *query vocabulary* (QueryParams/
PageResult) is shared across the whole codebase regardless of which
style a module's write side uses.
"""
from __future__ import annotations

from apps.identity.application.dtos import UserListQuery, UserSummaryResponse
from apps.identity.application.mappers import user_to_summary_response
from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.domain.repository import PageResult, QueryParams

_SEARCH_FIELDS = ("email",)
_DEFAULT_ORDERING = ("email",)


class ListUsersUseCase(UseCase[UserListQuery, PageResult[UserSummaryResponse]]):
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    def execute(self, request: UserListQuery) -> PageResult[UserSummaryResponse]:
        filters: dict[str, object] = {}
        if request.is_active is not None:
            filters["is_active"] = request.is_active

        page_result = self._users.list(
            QueryParams(
                filters=filters,
                search=request.search,
                search_fields=_SEARCH_FIELDS,
                ordering=request.ordering or _DEFAULT_ORDERING,
                page=request.page,
                page_size=request.page_size,
            )
        )
        return PageResult(
            items=[user_to_summary_response(u) for u in page_result.items],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )
