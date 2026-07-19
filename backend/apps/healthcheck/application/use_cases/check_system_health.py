"""Orchestrates infrastructure checks into a single overall health result."""
from __future__ import annotations

from apps.healthcheck.application.dtos import HealthCheckResult
from apps.healthcheck.infrastructure.checks import check_database, check_redis
from shared_kernel.application.base_use_case import UseCase


class CheckSystemHealthUseCase(UseCase[None, HealthCheckResult]):
    def execute(self, request: None = None) -> HealthCheckResult:
        components = [check_database(), check_redis()]
        overall_healthy = all(component.healthy for component in components)
        return HealthCheckResult(healthy=overall_healthy, components=components)
