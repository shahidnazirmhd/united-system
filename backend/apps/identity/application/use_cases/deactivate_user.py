"""Backs POST /auth/users/{id}/deactivate/. `is_active` is checked fresh
on every authenticated request (see IDENTITY_API.md's architecture
notes), so this takes effect immediately — no separate token-revocation
step is needed here, unlike a password change (which also has to rotate
`password_changed_at` to invalidate already-issued tokens)."""
from __future__ import annotations

import uuid

from apps.identity.application.dtos import UserSummaryResponse
from apps.identity.application.mappers import user_to_summary_response
from apps.identity.domain.exceptions import UserNotFoundError
from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.unit_of_work import UnitOfWork


class DeactivateUserUseCase(UseCase[uuid.UUID, UserSummaryResponse]):
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._uow = unit_of_work

    def execute(self, request: uuid.UUID) -> UserSummaryResponse:
        existing = self._users.get_by_id(request)
        if existing is None:
            raise UserNotFoundError()
        with self._uow:
            saved = self._users.save(existing.deactivate())
        return user_to_summary_response(saved)
