"""Unit test for the health check use case — no real DB/Redis connection,
both dependency checks are mocked so this runs in milliseconds with no
external services required."""
from __future__ import annotations

from unittest.mock import patch

from apps.healthcheck.application.dtos import ComponentStatus
from apps.healthcheck.application.use_cases.check_system_health import CheckSystemHealthUseCase

CHECK_DB = "apps.healthcheck.application.use_cases.check_system_health.check_database"
CHECK_REDIS = "apps.healthcheck.application.use_cases.check_system_health.check_redis"


def test_overall_health_is_true_when_all_components_are_healthy() -> None:
    with (
        patch(CHECK_DB, return_value=ComponentStatus(name="database", healthy=True)),
        patch(CHECK_REDIS, return_value=ComponentStatus(name="redis", healthy=True)),
    ):
        result = CheckSystemHealthUseCase().execute()

    assert result.healthy is True
    assert all(component.healthy for component in result.components)


def test_overall_health_is_false_when_any_component_is_unhealthy() -> None:
    with (
        patch(
            CHECK_DB,
            return_value=ComponentStatus(name="database", healthy=False, detail="connection refused"),
        ),
        patch(CHECK_REDIS, return_value=ComponentStatus(name="redis", healthy=True)),
    ):
        result = CheckSystemHealthUseCase().execute()

    assert result.healthy is False
    unhealthy = [c for c in result.components if not c.healthy]
    assert len(unhealthy) == 1
    assert unhealthy[0].name == "database"
    assert unhealthy[0].detail == "connection refused"
