"""Unit tests for LoginUserUseCase — every dependency is a hand-rolled fake,
no Django, no database, no Redis. This is what "domain/application logic is
testable without infrastructure" (HRMS_Architecture.md section 1.2) looks
like in practice.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from apps.identity.application.dtos import LoginRequest
from apps.identity.application.ports import PasswordHasherPort, TokenPair, TokenServicePort
from apps.identity.domain.entities import User
from apps.identity.domain.exceptions import InactiveUserError, InvalidCredentialsError
from apps.identity.domain.value_objects import Email
from apps.identity.application.use_cases.login_user import LoginUserUseCase
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork


class FakePasswordHasher(PasswordHasherPort):
    def hash(self, raw_password: str) -> str:
        return f"hashed:{raw_password}"

    def verify(self, raw_password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{raw_password}"


class FakeTokenService(TokenServicePort):
    def issue_pair(self, *, user_id, email):
        return TokenPair(access_token="access.tok", refresh_token="refresh.tok", access_expires_in_seconds=900)

    def decode(self, token):
        raise NotImplementedError


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


class FakeUserRepository:
    def __init__(self, user: User | None):
        self._user = user
        self.saved = None

    def get_by_email(self, email: Email) -> User | None:
        return self._user

    def save(self, user: User) -> User:
        self.saved = user
        return user


@pytest.fixture
def active_user() -> User:
    return User(
        id=uuid.uuid4(),
        email=Email("someone@example.com"),
        password_hash="hashed:correct-password",
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
    )


def test_login_succeeds_with_correct_credentials(active_user: User) -> None:
    use_case = LoginUserUseCase(
        user_repository=FakeUserRepository(active_user),
        password_hasher=FakePasswordHasher(),
        token_service=FakeTokenService(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    result = use_case.execute(LoginRequest(email="someone@example.com", password="correct-password"))

    assert result.access_token == "access.tok"
    assert result.refresh_token == "refresh.tok"
    assert result.token_type == "Bearer"


def test_login_fails_with_wrong_password(active_user: User) -> None:
    use_case = LoginUserUseCase(
        user_repository=FakeUserRepository(active_user),
        password_hasher=FakePasswordHasher(),
        token_service=FakeTokenService(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(InvalidCredentialsError):
        use_case.execute(LoginRequest(email="someone@example.com", password="wrong-password"))


def test_login_fails_when_user_does_not_exist() -> None:
    use_case = LoginUserUseCase(
        user_repository=FakeUserRepository(None),
        password_hasher=FakePasswordHasher(),
        token_service=FakeTokenService(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(InvalidCredentialsError):
        use_case.execute(LoginRequest(email="nobody@example.com", password="anything"))


def test_login_fails_when_user_is_inactive(active_user: User) -> None:
    inactive_user = User(
        id=active_user.id,
        email=active_user.email,
        password_hash=active_user.password_hash,
        is_active=False,
        password_changed_at=active_user.password_changed_at,
    )
    use_case = LoginUserUseCase(
        user_repository=FakeUserRepository(inactive_user),
        password_hasher=FakePasswordHasher(),
        token_service=FakeTokenService(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )

    with pytest.raises(InactiveUserError):
        use_case.execute(LoginRequest(email="someone@example.com", password="correct-password"))
