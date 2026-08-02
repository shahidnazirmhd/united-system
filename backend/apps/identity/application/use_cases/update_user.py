"""Admin edit of a user's email — backs PATCH /auth/users/{id}/. Password
and roles are deliberately untouched here — see UpdateUserRequest's
docstring."""
from __future__ import annotations

from apps.identity.application.dtos import UpdateUserRequest, UserSummaryResponse
from apps.identity.application.mappers import user_to_summary_response
from apps.identity.domain.exceptions import DuplicateEmailError, UserNotFoundError
from apps.identity.domain.repositories import UserRepository
from apps.identity.domain.value_objects import Email
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.unit_of_work import UnitOfWork


class UpdateUserUseCase(UseCase[UpdateUserRequest, UserSummaryResponse]):
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._uow = unit_of_work

    def execute(self, request: UpdateUserRequest) -> UserSummaryResponse:
        existing = self._users.get_by_id(request.user_id)
        if existing is None:
            raise UserNotFoundError()

        new_email = Email(request.email)
        if str(existing.email) != str(new_email):
            holder = self._users.get_by_email(new_email)
            if holder is not None and holder.id != existing.id:
                raise DuplicateEmailError()

        updated = existing.with_profile(email=new_email)
        with self._uow:
            saved = self._users.save(updated)
        return user_to_summary_response(saved)
