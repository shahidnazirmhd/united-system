"""Reverses deactivate_user.py — backs POST /auth/users/{id}/activate/."""
from __future__ import annotations

import uuid

from apps.identity.application.dtos import UserSummaryResponse
from apps.identity.application.mappers import user_to_summary_response
from apps.identity.domain.exceptions import UserNotFoundError
from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.unit_of_work import UnitOfWork


class ActivateUserUseCase(UseCase[uuid.UUID, UserSummaryResponse]):
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._uow = unit_of_work

    def execute(self, request: uuid.UUID) -> UserSummaryResponse:
        existing = self._users.get_by_id(request)
        if existing is None:
            raise UserNotFoundError()
        with self._uow:
            saved = self._users.save(existing.activate())
        return user_to_summary_response(saved)
