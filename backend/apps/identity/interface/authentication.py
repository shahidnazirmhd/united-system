"""Custom DRF authentication class.

Does not use django.contrib.auth or simplejwt's JWTAuthentication — both
assume a Django auth User resolvable via get_user_model(), which this
project deliberately does not install (see this phase's delivery notes).
Instead this decodes the bearer token via TokenServicePort, checks the
blocklist, loads the user in a single query, and returns a shared_kernel
AuthenticatedPrincipal — not a Django model instance — as request.user.

No caching layer here, on purpose: is_active and password_changed_at must be
checked fresh on every request (that's what makes deactivation and password
resets take effect immediately rather than after some staleness window), so
there is no DB round-trip left to save by caching the rest of the lookup —
it's already one query either way (get_by_id uses prefetch_related). Adding
a cache that doesn't remove the query it would need to bypass for
correctness is complexity with no payoff.
"""
from __future__ import annotations

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.identity.domain.exceptions import InvalidTokenError
from apps.identity.infrastructure.jwt_service import PyJWTTokenService
from apps.identity.infrastructure.repositories import DjangoUserRepository
from apps.identity.infrastructure.token_blocklist import RedisTokenBlocklist
from shared_kernel.api.principal import AuthenticatedPrincipal


class JWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def __init__(self) -> None:
        self._token_service = PyJWTTokenService()
        self._blocklist = RedisTokenBlocklist()
        self._users = DjangoUserRepository()

    def authenticate(self, request: Request) -> tuple[AuthenticatedPrincipal, str] | None:
        header = request.headers.get("Authorization", "")
        if not header.startswith(f"{self.keyword} "):
            return None  # no credentials supplied — let other authenticators / AllowAny decide

        raw_token = header[len(self.keyword) + 1 :].strip()
        if not raw_token:
            return None

        try:
            decoded = self._token_service.decode(raw_token)
        except InvalidTokenError as exc:
            raise AuthenticationFailed(str(exc), code="invalid_token") from exc

        if decoded.token_type != "access":
            raise AuthenticationFailed("A refresh token cannot be used to authenticate requests.")

        if self._blocklist.is_revoked(decoded.jti):
            raise AuthenticationFailed("This token has been revoked.", code="token_revoked")

        user = self._users.get_by_id(decoded.user_id)
        if user is None:
            raise AuthenticationFailed("This account no longer exists.")
        if not user.is_active:
            raise AuthenticationFailed("This account has been deactivated.", code="inactive_user")
        # decoded.issued_at is reconstructed from the JWT's "iat" claim, which
        # is an integer Unix timestamp (RFC 7519 NumericDate — whole seconds
        # only), while password_changed_at is a Postgres timestamp with
        # microsecond precision. Comparing them raw means any login that
        # happens in the same wall-clock second as the account's
        # password_changed_at value (e.g. logging in immediately after
        # account creation, since password_changed_at is auto_now_add at
        # creation time — exactly what every test fixture and most first-time
        # logins do) spuriously fails this check: the truncated iat rounds
        # down to the start of that second, which is almost always "before"
        # the microsecond-precise password_changed_at, even though the login
        # genuinely happened after. Truncating password_changed_at to the
        # same whole-second precision before comparing removes that false
        # positive while still correctly rejecting any token issued in an
        # earlier second than the password change.
        if decoded.issued_at < user.password_changed_at.replace(microsecond=0):
            raise AuthenticationFailed(
                "This session was invalidated by a password change.", code="token_revoked"
            )

        principal = AuthenticatedPrincipal(
            user_id=user.id,
            email=str(user.email),
            role_names=user.role_names,
            permission_codes=user.permission_codes,
        )
        # jti is returned as the "auth" element of the tuple so views/use
        # cases that need it (logout) can read it off request.auth without
        # re-decoding the token themselves.
        return principal, decoded.jti

    def authenticate_header(self, request: Request) -> str:
        return self.keyword
