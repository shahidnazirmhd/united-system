"""Infrastructure-level connectivity checks.

Each function verifies exactly one dependency is reachable and reports back
— no aggregation or pass/fail decision-making here, that belongs to the use
case that calls these (apps/healthcheck/application/use_cases).
"""
from __future__ import annotations

from django.db import connections
from django.db.utils import OperationalError

from apps.healthcheck.application.dtos import ComponentStatus


def check_database() -> ComponentStatus:
    try:
        connection = connections["default"]
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return ComponentStatus(name="database", healthy=True)
    except OperationalError as exc:
        return ComponentStatus(name="database", healthy=False, detail=str(exc))


def check_redis() -> ComponentStatus:
    try:
        from django.core.cache import cache

        probe_key = "__healthcheck__"
        cache.set(probe_key, "ok", timeout=5)
        if cache.get(probe_key) != "ok":
            raise ConnectionError("Redis cache set/get round-trip failed")
        return ComponentStatus(name="redis", healthy=True)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: this is a liveness probe
        return ComponentStatus(name="redis", healthy=False, detail=str(exc))
