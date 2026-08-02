"""Returns any user's profile by id — backs the admin-facing
GET /auth/users/{id}/, gated behind identity.view_users.

Deliberately a separate class from `GetCurrentUserUseCase` despite nearly
identical logic: that one backs the self-service `GET /auth/me/`, which
needs no permission at all (a strictly smaller grant than "view anyone's
record") — the same "self-service vs. admin-gated" split
EMPLOYEE_API.md's `GET /employees/me/` vs. `GET /employees/{id}/`
documents. Keeping two classes documents that authorization distinction
directly in the code, not just in a view's permission_classes.
"""
from __future__ import annotations

import uuid

from apps.identity.application.dtos import UserSummaryResponse
from apps.identity.application.mappers import user_to_summary_response
from apps.identity.domain.exceptions import UserNotFoundError
from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase


class GetUserByIdUseCase(UseCase[uuid.UUID, UserSummaryResponse]):
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    def execute(self, request: uuid.UUID) -> UserSummaryResponse:
        user = self._users.get_by_id(request)
        if user is None:
            raise UserNotFoundError()
        return user_to_summary_response(user)
