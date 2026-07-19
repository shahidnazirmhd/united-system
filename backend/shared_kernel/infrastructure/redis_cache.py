"""Thin wrapper around Django's configured cache backend.

Application-layer code depends on this narrow interface instead of importing
`django.core.cache.cache` directly everywhere — keeps the caching technology
swappable and makes every place the application layer touches this
cross-cutting infrastructure concern easy to find.
"""
from __future__ import annotations

from typing import Any

from django.core.cache import cache


class CacheClient:
    def get(self, key: str, default: Any = None) -> Any:
        return cache.get(key, default)

    def set(self, key: str, value: Any, timeout_seconds: int = 300) -> None:
        cache.set(key, value, timeout_seconds)

    def delete(self, key: str) -> None:
        cache.delete(key)


cache_client = CacheClient()
