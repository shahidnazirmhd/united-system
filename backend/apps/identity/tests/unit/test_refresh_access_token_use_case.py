"""Unit tests for RefreshAccessTokenUseCase, covering the two security
properties that matter most here: rotation (old token gets blocklisted) and
the password_changed_at check that makes a password reset invalidate
existing sessions even though the refresh token itself hasn't expired.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from apps.identity.application.dtos import RefreshRequest
from apps.identity.application.ports import DecodedToken, TokenPair
from apps.identity.application.use_cases.refresh_access_token import RefreshAccessTokenUseCase
from apps.identity.domain.entities import User
from apps.identity.domain.exceptions import TokenRevokedError
from apps.identity.domain.value_objects import Email


@dataclass
class FakeTokenService:
    decoded: DecodedToken

    def decode(self, token: str) -> DecodedToken:
        return self.decoded

    def issue_pair(self, *, user_id, email) -> TokenPair:
        return TokenPair(access_token="new.access", refresh_token="new.refresh", access_expires_in_seconds=900)


class FakeBlocklist:
    def __init__(self):
        self.revoked: list[str] = []

    def revoke(self, jti, *, ttl):
        self.revoked.append(jti)

    def is_revoked(self, jti):
        return jti in self.revoked


class FakeUserRepository:
    def __init__(self, user: User):
        self._user = user

    def get_by_id(self, user_id):
        return self._user


def _make_decoded_token(*, issued_at: datetime, user_id: uuid.UUID) -> DecodedToken:
    return DecodedToken(
        user_id=user_id,
        token_type="refresh",
        jti=str(uuid.uuid4()),
        issued_at=issued_at,
        expires_at=issued_at + timedelta(days=7),
    )


def test_refresh_rotates_the_old_refresh_token() -> None:
    user_id = uuid.uuid4()
    password_changed_at = datetime.now(timezone.utc) - timedelta(days=30)
    decoded = _make_decoded_token(issued_at=datetime.now(timezone.utc), user_id=user_id)
    user = User(
        id=user_id,
        email=Email("someone@example.com"),
        password_hash="irrelevant",
        password_changed_at=password_changed_at,
    )
    blocklist = FakeBlocklist()

    use_case = RefreshAccessTokenUseCase(
        user_repository=FakeUserRepository(user),
        token_service=FakeTokenService(decoded=decoded),
        token_blocklist=blocklist,
    )

    result = use_case.execute(RefreshRequest(refresh_token="whatever"))

    assert result.access_token == "new.access"
    assert decoded.jti in blocklist.revoked


def test_refresh_rejects_token_issued_before_password_change() -> None:
    user_id = uuid.uuid4()
    token_issued_at = datetime.now(timezone.utc) - timedelta(days=1)
    password_changed_at = datetime.now(timezone.utc)  # changed AFTER the token was issued
    decoded = _make_decoded_token(issued_at=token_issued_at, user_id=user_id)
    user = User(
        id=user_id,
        email=Email("someone@example.com"),
        password_hash="irrelevant",
        password_changed_at=password_changed_at,
    )

    use_case = RefreshAccessTokenUseCase(
        user_repository=FakeUserRepository(user),
        token_service=FakeTokenService(decoded=decoded),
        token_blocklist=FakeBlocklist(),
    )

    with pytest.raises(TokenRevokedError):
        use_case.execute(RefreshRequest(refresh_token="whatever"))
