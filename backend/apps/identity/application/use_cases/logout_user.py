"""Logout use case.

Revokes the presented refresh token immediately (rather than waiting for it
to expire naturally), and the current access token too if its jti was
supplied — so "logout" actually invalidates the session rather than just
discarding tokens client-side that would otherwise keep working until they
expire.
"""
from __future__ import annotations

from datetime import datetime, timezone

from apps.identity.application.dtos import LogoutRequest
from apps.identity.application.ports import TokenBlocklistPort, TokenServicePort
from apps.identity.domain.events import UserLoggedOut
from shared_kernel.application.base_use_case import UseCase
from shared_kernel.application.event_bus import EventBus


class LogoutUserUseCase(UseCase[LogoutRequest, None]):
    def __init__(
        self,
        token_service: TokenServicePort,
        token_blocklist: TokenBlocklistPort,
        event_bus: EventBus,
    ) -> None:
        self._tokens = token_service
        self._blocklist = token_blocklist
        self._event_bus = event_bus

    def execute(self, request: LogoutRequest) -> None:
        decoded_refresh = self._tokens.decode(request.refresh_token)
        remaining = decoded_refresh.expires_at - datetime.now(timezone.utc)
        if remaining.total_seconds() > 0:
            self._blocklist.revoke(decoded_refresh.jti, ttl=remaining)

        if request.access_token_jti:
            # The access token's own remaining lifetime is short (minutes),
            # so a conservative fixed TTL is fine here without decoding it
            # again — the caller already proved they hold a valid access
            # token simply by reaching this authenticated endpoint.
            from datetime import timedelta

            self._blocklist.revoke(request.access_token_jti, ttl=timedelta(minutes=30))

        self._event_bus.publish(UserLoggedOut(user_id=decoded_refresh.user_id))
