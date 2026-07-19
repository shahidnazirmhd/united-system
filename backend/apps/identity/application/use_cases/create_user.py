"""Creates a new authentication account.

Not exposed as public self-service signup in this phase — gated behind the
identity.manage_users permission (see interface/views.py) and used for
provisioning accounts for people/systems that need one, independently of
whether they ever become an Employee (see this phase's architecture notes on
why User and Employee are separate).
"""
from __future__ import annotations

import uuid

from apps.identity.application.dtos import CreateUserRequest, RoleSummary, UserSummaryResponse
from apps.identity.application.ports import PasswordHasherPort
from apps.identity.domain.entities import User
from apps.identity.domain.exceptions import DuplicateEmailError
from apps.identity.domain.repositories import UserRepository
from apps.identity.domain.value_objects import Email
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.uuid7 import generate_uuid7


class CreateUserUseCase(UseCase[CreateUserRequest, UserSummaryResponse]):
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasherPort,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._users = user_repository
        self._hasher = password_hasher
        self._uow = unit_of_work

    def execute(self, request: CreateUserRequest) -> UserSummaryResponse:
        email = Email(request.email)
        if self._users.exists_with_email(email):
            raise DuplicateEmailError()

        user = User(
            id=generate_uuid7(),
            email=email,
            password_hash=self._hasher.hash(request.password),
            is_system_account=request.is_system_account,
        )

        with self._uow:
            saved = self._users.save(user)

        return UserSummaryResponse(
            id=saved.id,
            email=str(saved.email),
            is_active=saved.is_active,
            is_system_account=saved.is_system_account,
            employee_id=saved.employee_id,
            roles=tuple(RoleSummary(id=r.id, name=r.name) for r in saved.roles),
            permission_codes=saved.permission_codes,
        )
