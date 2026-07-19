"""JWT issuance/verification via PyJWT directly.

Deliberately not djangorestframework-simplejwt: simplejwt's authentication
class and its `Token.for_user()`/`get_user()` helpers are built around
`django.contrib.auth.get_user_model()`, which this project doesn't install
(see this phase's delivery notes). PyJWT is a lower-level, framework-agnostic
library — full control over claims, zero coupling to Django's auth system,
and the only thing the rest of the codebase depends on is the
TokenServicePort interface, so this choice is swappable later without
touching a single use case.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from django.conf import settings

from apps.identity.application.ports import DecodedToken, TokenPair, TokenServicePort
from apps.identity.domain.exceptions import InvalidTokenError


class PyJWTTokenService(TokenServicePort):
    def __init__(
        self,
        *,
        signing_key: str | None = None,
        algorithm: str | None = None,
        access_lifetime: timedelta | None = None,
        refresh_lifetime: timedelta | None = None,
    ) -> None:
        self._signing_key = signing_key or settings.JWT_SIGNING_KEY
        self._algorithm = algorithm or settings.JWT_ALGORITHM
        self._access_lifetime = access_lifetime or timedelta(minutes=settings.JWT_ACCESS_TOKEN_LIFETIME_MINUTES)
        self._refresh_lifetime = refresh_lifetime or timedelta(days=settings.JWT_REFRESH_TOKEN_LIFETIME_DAYS)

    def issue_pair(self, *, user_id: uuid.UUID, email: str) -> TokenPair:
        now = datetime.now(timezone.utc)

        access_token = self._encode(
            user_id=user_id, email=email, token_type="access", now=now, lifetime=self._access_lifetime
        )
        refresh_token = self._encode(
            user_id=user_id, email=email, token_type="refresh", now=now, lifetime=self._refresh_lifetime
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_in_seconds=int(self._access_lifetime.total_seconds()),
        )

    def decode(self, token: str) -> DecodedToken:
        try:
            payload = jwt.decode(token, self._signing_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise InvalidTokenError("This token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError("This token is malformed or has an invalid signature.") from exc

        try:
            return DecodedToken(
                user_id=uuid.UUID(payload["sub"]),
                token_type=payload["type"],
                jti=payload["jti"],
                issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidTokenError("This token is missing required claims.") from exc

    def _encode(
        self,
        *,
        user_id: uuid.UUID,
        email: str,
        token_type: str,
        now: datetime,
        lifetime: timedelta,
    ) -> str:
        payload = {
            "sub": str(user_id),
            "email": email,
            "type": token_type,
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + lifetime).timestamp()),
        }
        return jwt.encode(payload, self._signing_key, algorithm=self._algorithm)
