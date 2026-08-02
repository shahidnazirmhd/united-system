"""Returns the authenticated caller's own profile — backs GET /auth/me/."""
from __future__ import annotations

import uuid

from apps.identity.application.dtos import UserSummaryResponse
from apps.identity.application.mappers import user_to_summary_response
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
        return user_to_summary_response(user)
