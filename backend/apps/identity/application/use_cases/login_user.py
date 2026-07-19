"""Login use case.

Deliberately returns the same InvalidCredentialsError whether the email
doesn't exist or the password is wrong — distinguishing the two in the
response would let an attacker enumerate valid email addresses.
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.identity.application.dtos import LoginRequest, TokenPairResponse
from apps.identity.application.ports import PasswordHasherPort, TokenServicePort
from apps.identity.domain.entities import User
from apps.identity.domain.events import UserLoggedIn
from apps.identity.domain.exceptions import InactiveUserError, InvalidCredentialsError
from apps.identity.domain.repositories import UserRepository
from apps.identity.domain.value_objects import Email
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork


class LoginUserUseCase(UseCase[LoginRequest, TokenPairResponse]):
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasherPort,
        token_service: TokenServicePort,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        self._users = user_repository
        self._hasher = password_hasher
        self._tokens = token_service
        self._uow = unit_of_work
        self._event_bus = event_bus

    def execute(self, request: LoginRequest) -> TokenPairResponse:
        user = self._users.get_by_email(Email(request.email))
        if user is None:
            raise InvalidCredentialsError()

        if not self._hasher.verify(request.password, user.password_hash):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        with self._uow:
            updated_user = User(
                id=user.id,
                email=user.email,
                password_hash=user.password_hash,
                is_active=user.is_active,
                is_system_account=user.is_system_account,
                employee_id=user.employee_id,
                last_login_at=datetime.now(timezone.utc),
                password_changed_at=user.password_changed_at,
                roles=user.roles,
            )
            self._users.save(updated_user)

        pair = self._tokens.issue_pair(user_id=user.id, email=str(user.email))
        self._event_bus.publish(UserLoggedIn(user_id=user.id, source=request.source))

        return TokenPairResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type="Bearer",
            expires_in=pair.access_expires_in_seconds,
        )
