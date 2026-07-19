"""Per-chat soft rate limiting at the webhook layer.

Per the Phase 7 brief's "rate-limiting readiness" requirement and
HRMS_Architecture.md section 7's note that the Gateway needs no bespoke
protection beyond standard measures since "it's not a privileged internal
service." Telegram already flood-limits per-chat sends on its own side; this
is a second, independent layer specifically against a compromised or
malfunctioning client hammering *this* service's webhook endpoint (and, by
extension, the backend behind it) faster than Telegram's own limits would
catch, using a plain fixed-window counter — the simplest correct
implementation for a rate this low (default: `TELEGRAM_GATEWAY_RATE_LIMIT_
PER_CHAT_PER_MINUTE`), not a token-bucket, since a burst tolerance more
sophisticated than "N per rolling minute" isn't needed at this volume.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type hint only — see auth/account_linking.py's identical note.
    import redis.asyncio as redis

_KEY_PREFIX = "telegram_gateway:ratelimit:"
_WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(self, redis_client: redis.Redis, *, limit_per_window: int) -> None:
        self._redis = redis_client
        self._limit = limit_per_window

    async def is_allowed(self, chat_id: int) -> bool:
        key = f"{_KEY_PREFIX}{chat_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, _WINDOW_SECONDS)
        return count <= self._limit
