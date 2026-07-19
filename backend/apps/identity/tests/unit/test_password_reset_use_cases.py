"""Unit tests for the password reset flow: request (always succeeds
silently) and confirm (validates the token, rejects expired/used tokens,
stamps password_changed_at)."""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from apps.identity.application.dtos import ConfirmPasswordResetRequest, RequestPasswordResetRequest
from apps.identity.application.ports import PasswordHasherPort
from apps.identity.application.use_cases.confirm_password_reset import ConfirmPasswordResetUseCase
from apps.identity.application.use_cases.request_password_reset import RequestPasswordResetUseCase
from apps.identity.domain.entities import PasswordResetToken, User
from apps.identity.domain.exceptions import ExpiredResetTokenError, InvalidResetTokenError
from apps.identity.domain.value_objects import Email
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork


class FakeUnitOfWork(UnitOfWork):
    def commit(self):
        pass

    def rollback(self):
        pass


class FakeEventBus(EventBus):
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)

    def subscribe(self, event_type, handler):
        pass


class FakeHasher(PasswordHasherPort):
    def hash(self, raw_password):
        return f"hashed:{raw_password}"

    def verify(self, raw_password, password_hash):
        return password_hash == f"hashed:{raw_password}"


class FakeUserRepository:
    def __init__(self, user):
        self._user = user
        self.saved = None

    def get_by_email(self, email):
        return self._user

    def get_by_id(self, user_id):
        return self._user

    def save(self, user):
        self.saved = user
        return user


class FakeEmailSender:
    def __init__(self):
        self.sent = []

    def send_password_reset_email(self, *, to_email, raw_token):
        self.sent.append((to_email, raw_token))


class FakeResetTokenRepository:
    def __init__(self, existing: PasswordResetToken | None = None):
        self._existing = existing
        self.created = None
        self.marked_used = None

    def create(self, user_id, token_hash, expires_at):
        self.created = (user_id, token_hash, expires_at)
        return PasswordResetToken(id=uuid.uuid4(), user_id=user_id, token_hash=token_hash, expires_at=expires_at)

    def get_by_hash(self, token_hash):
        return self._existing

    def mark_used(self, token_hash, *, used_at):
        self.marked_used = (token_hash, used_at)


def test_request_password_reset_sends_email_for_existing_user() -> None:
    user = User(id=uuid.uuid4(), email=Email("someone@example.com"), password_hash="x")
    email_sender = FakeEmailSender()
    reset_tokens = FakeResetTokenRepository()

    use_case = RequestPasswordResetUseCase(
        user_repository=FakeUserRepository(user),
        reset_token_repository=reset_tokens,
        email_sender=email_sender,
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    use_case.execute(RequestPasswordResetRequest(email="someone@example.com"))

    assert len(email_sender.sent) == 1
    assert email_sender.sent[0][0] == "someone@example.com"
    assert reset_tokens.created is not None


def test_request_password_reset_is_silent_for_unknown_email() -> None:
    email_sender = FakeEmailSender()
    use_case = RequestPasswordResetUseCase(
        user_repository=FakeUserRepository(None),
        reset_token_repository=FakeResetTokenRepository(),
        email_sender=email_sender,
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    use_case.execute(RequestPasswordResetRequest(email="nobody@example.com"))  # must not raise

    assert email_sender.sent == []


def test_confirm_password_reset_rejects_expired_token() -> None:
    user = User(id=uuid.uuid4(), email=Email("someone@example.com"), password_hash="old-hash")
    raw_token = "some-raw-token"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expired_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    use_case = ConfirmPasswordResetUseCase(
        user_repository=FakeUserRepository(user),
        reset_token_repository=FakeResetTokenRepository(existing=expired_token),
        password_hasher=FakeHasher(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(ExpiredResetTokenError):
        use_case.execute(ConfirmPasswordResetRequest(token=raw_token, new_password="new-password-123"))


def test_confirm_password_reset_rejects_unknown_token() -> None:
    use_case = ConfirmPasswordResetUseCase(
        user_repository=FakeUserRepository(None),
        reset_token_repository=FakeResetTokenRepository(existing=None),
        password_hasher=FakeHasher(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(InvalidResetTokenError):
        use_case.execute(ConfirmPasswordResetRequest(token="anything", new_password="new-password-123"))


def test_confirm_password_reset_updates_password_and_marks_token_used() -> None:
    user = User(id=uuid.uuid4(), email=Email("someone@example.com"), password_hash="old-hash")
    raw_token = "some-raw-token"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    valid_token = PasswordResetToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    users = FakeUserRepository(user)
    reset_tokens = FakeResetTokenRepository(existing=valid_token)

    use_case = ConfirmPasswordResetUseCase(
        user_repository=users,
        reset_token_repository=reset_tokens,
        password_hasher=FakeHasher(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    use_case.execute(ConfirmPasswordResetRequest(token=raw_token, new_password="new-password-123"))

    assert users.saved.password_hash == "hashed:new-password-123"
    assert reset_tokens.marked_used[0] == token_hash
