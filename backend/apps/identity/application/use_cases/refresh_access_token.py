"""Token refresh use case.

Refresh tokens rotate on every use: the presented one is immediately
blocklisted and a brand new access+refresh pair is issued. A refresh token
that gets used twice (e.g. stolen and replayed after the legitimate client
already rotated it) is rejected outright — see TokenRevokedError below.
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.identity.application.dtos import RefreshRequest, TokenPairResponse
from apps.identity.application.ports import TokenBlocklistPort, TokenServicePort
from apps.identity.domain.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    TokenRevokedError,
    UserNotFoundError,
)
from apps.identity.domain.repositories import UserRepository
from shared_kernel.application.base_use_case import UseCase


class RefreshAccessTokenUseCase(UseCase[RefreshRequest, TokenPairResponse]):
    def __init__(
        self,
        user_repository: UserRepository,
        token_service: TokenServicePort,
        token_blocklist: TokenBlocklistPort,
    ) -> None:
        self._users = user_repository
        self._tokens = token_service
        self._blocklist = token_blocklist

    def execute(self, request: RefreshRequest) -> TokenPairResponse:
        decoded = self._tokens.decode(request.refresh_token)
        if decoded.token_type != "refresh":
            raise InvalidTokenError("This is not a refresh token.")

        if self._blocklist.is_revoked(decoded.jti):
            raise TokenRevokedError()

        user = self._users.get_by_id(decoded.user_id)
        if user is None:
            raise UserNotFoundError()
        if not user.is_active:
            raise InactiveUserError()
        # See apps/identity/interface/authentication.py's identical check for
        # why password_changed_at is truncated to whole-second precision
        # before this comparison: the JWT "iat" claim decoded.issued_at comes
        # from is itself only second-precision (RFC 7519 NumericDate), so
        # comparing it against a microsecond-precise database timestamp
        # spuriously rejects tokens issued in the same wall-clock second as
        # password_changed_at — most commonly right after account creation.
        if decoded.issued_at < user.password_changed_at.replace(microsecond=0):
            # The password was changed after this refresh token was issued —
            # see the password_changed_at field on the User entity for why
            # this is the mechanism that makes a password reset actually
            # invalidate existing sessions.
            raise TokenRevokedError("This session was invalidated by a password change.")

        remaining = decoded.expires_at - datetime.now(timezone.utc)
        if remaining.total_seconds() > 0:
            self._blocklist.revoke(decoded.jti, ttl=remaining)

        pair = self._tokens.issue_pair(user_id=user.id, email=str(user.email))
        return TokenPairResponse(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type="Bearer",
            expires_in=pair.access_expires_in_seconds,
        )
