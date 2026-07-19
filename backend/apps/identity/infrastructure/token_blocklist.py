"""Redis-backed token revocation list.

Uses REDIS_TOKEN_BLOCKLIST_URL (its own logical Redis DB, separate from the
cache and Celery broker/backend — see config/settings/base.py) rather than
Django's default cache, so revocation entries can't be evicted by unrelated
cache pressure and can be monitored/sized independently in production.
Entries are stored with a TTL matching the token's own remaining lifetime,
so the blocklist never accumulates stale entries for tokens that have
already naturally expired.
"""
from __future__ import annotations

from datetime import timedelta

import redis
from django.conf import settings

from apps.identity.application.ports import TokenBlocklistPort

_KEY_PREFIX = "token_blocklist:"


class RedisTokenBlocklist(TokenBlocklistPort):
    def __init__(self, redis_url: str | None = None) -> None:
        self._client = redis.Redis.from_url(redis_url or settings.REDIS_TOKEN_BLOCKLIST_URL)

    def revoke(self, jti: str, *, ttl: timedelta) -> None:
        ttl_seconds = max(int(ttl.total_seconds()), 1)
        self._client.set(f"{_KEY_PREFIX}{jti}", "1", ex=ttl_seconds)

    def is_revoked(self, jti: str) -> bool:
        return self._client.exists(f"{_KEY_PREFIX}{jti}") == 1
