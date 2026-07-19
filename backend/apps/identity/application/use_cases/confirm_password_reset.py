"""Completes a password reset: verifies the token, sets the new password,
and stamps password_changed_at so every existing access/refresh token
becomes invalid immediately (see refresh_access_token.py and
interface/authentication.py for where that stamp is checked).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from apps.identity.application.dtos import ConfirmPasswordResetRequest
from apps.identity.application.ports import PasswordHasherPort
from apps.identity.domain.entities import User
from apps.identity.domain.events import PasswordChanged
from apps.identity.domain.exceptions import (
    ExpiredResetTokenError,
    InvalidResetTokenError,
    UserNotFoundError,
)
from apps.identity.domain.repositories import PasswordResetTokenRepository, UserRepository
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork


class ConfirmPasswordResetUseCase(UseCase[ConfirmPasswordResetRequest, None]):
    def __init__(
        self,
        user_repository: UserRepository,
        reset_token_repository: PasswordResetTokenRepository,
        password_hasher: PasswordHasherPort,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        self._users = user_repository
        self._reset_tokens = reset_token_repository
        self._hasher = password_hasher
        self._uow = unit_of_work
        self._event_bus = event_bus

    def execute(self, request: ConfirmPasswordResetRequest) -> None:
        token_hash = hashlib.sha256(request.token.encode("utf-8")).hexdigest()
        token = self._reset_tokens.get_by_hash(token_hash)

        if token is None or token.used_at is not None:
            raise InvalidResetTokenError()

        now = datetime.now(timezone.utc)
        if now >= token.expires_at:
            raise ExpiredResetTokenError()

        user = self._users.get_by_id(token.user_id)
        if user is None:
            raise UserNotFoundError()

        updated_user = User(
            id=user.id,
            email=user.email,
            password_hash=self._hasher.hash(request.new_password),
            is_active=user.is_active,
            is_system_account=user.is_system_account,
            employee_id=user.employee_id,
            last_login_at=user.last_login_at,
            password_changed_at=now,
            roles=user.roles,
        )

        with self._uow:
            self._users.save(updated_user)
            self._reset_tokens.mark_used(token_hash, used_at=now)

        self._event_bus.publish(PasswordChanged(user_id=user.id))
