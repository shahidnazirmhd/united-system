"""Integration test hitting the real health check endpoint, real DB
connection, and real Redis connection — requires the services defined in
infra/docker-compose.yml to be up (or equivalent local Postgres/Redis)."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_check_endpoint_returns_200_and_healthy_status() -> None:
    client = APIClient()
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.data["status"] == "healthy"
    assert response.data["components"]["database"]["healthy"] is True
    assert response.data["components"]["redis"]["healthy"] is True


@pytest.mark.django_db
def test_health_check_endpoint_requires_no_authentication() -> None:
    client = APIClient()  # no credentials set at all
    response = client.get("/health/")

    assert response.status_code != 401
    assert response.status_code != 403
