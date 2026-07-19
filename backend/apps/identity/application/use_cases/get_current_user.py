"""Returns the authenticated caller's own profile — backs GET /auth/me/."""
from __future__ import annotations

import uuid

from apps.identity.application.dtos import RoleSummary, UserSummaryResponse
from apps.identity.domain.exceptions import UserNotFoundError
from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase


class GetCurrentUserUseCase(UseCase[uuid.UUID, UserSummaryResponse]):
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    def execute(self, request: uuid.UUID) -> UserSummaryResponse:
        user = self._users.get_by_id(request)
        if user is None:
            raise UserNotFoundError()

        return UserSummaryResponse(
            id=user.id,
            email=str(user.email),
            is_active=user.is_active,
            is_system_account=user.is_system_account,
            employee_id=user.employee_id,
            roles=tuple(RoleSummary(id=role.id, name=role.name) for role in user.roles),
            permission_codes=user.permission_codes,
        )
