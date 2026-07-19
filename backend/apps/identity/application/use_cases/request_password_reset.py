"""Starts a password reset flow.

Always returns successfully whether or not the email belongs to a real
account — the interface layer's response is identical either way, so this
endpoint can't be used to enumerate registered email addresses. The raw
token is only ever handed to EmailSenderPort in-memory; only its SHA-256
hash is persisted (see infrastructure/repositories.py).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from apps.identity.application.dtos import RequestPasswordResetRequest
from apps.identity.application.ports import EmailSenderPort
from apps.identity.domain.events import PasswordResetRequested
from apps.identity.domain.repositories import PasswordResetTokenRepository, UserRepository
from apps.identity.domain.value_objects import Email
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork

RESET_TOKEN_LIFETIME = timedelta(minutes=30)


class RequestPasswordResetUseCase(UseCase[RequestPasswordResetRequest, None]):
    def __init__(
        self,
        user_repository: UserRepository,
        reset_token_repository: PasswordResetTokenRepository,
        email_sender: EmailSenderPort,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        self._users = user_repository
        self._reset_tokens = reset_token_repository
        self._email_sender = email_sender
        self._uow = unit_of_work
        self._event_bus = event_bus

    def execute(self, request: RequestPasswordResetRequest) -> None:
        try:
            user = self._users.get_by_email(Email(request.email))
        except ValueError:
            return  # malformed email — behave identically to "not found"

        if user is None:
            return

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = datetime.now(timezone.utc) + RESET_TOKEN_LIFETIME

        with self._uow:
            self._reset_tokens.create(user.id, token_hash, expires_at)

        self._email_sender.send_password_reset_email(to_email=str(user.email), raw_token=raw_token)
        self._event_bus.publish(PasswordResetRequested(user_id=user.id))
