"""Integration tests for the login/logout/refresh/me endpoints — real
Postgres, real Redis (via the services in infra/docker-compose.yml),
exercising the full stack from HTTP down to the database.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.identity.infrastructure.models import UserRecord
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher

pytestmark = pytest.mark.django_db


@pytest.fixture
def existing_user():
    hasher = DjangoPasswordHasher()
    return UserRecord.objects.create(
        email="integration.user@example.com",
        password_hash=hasher.hash("correct-horse-battery-staple"),
    )


def test_login_returns_token_pair_for_correct_credentials(existing_user) -> None:
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "integration.user@example.com", "password": "correct-horse-battery-staple"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["success"] is True
    assert "access_token" in response.data["data"]
    assert "refresh_token" in response.data["data"]


def test_login_rejects_wrong_password(existing_user) -> None:
    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {"email": "integration.user@example.com", "password": "wrong-password"},
        format="json",
    )

    assert response.status_code == 401
    assert response.data["success"] is False
    assert response.data["error"]["code"] == "invalid_credentials"


def test_me_requires_authentication() -> None:
    client = APIClient()

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401


def test_full_login_me_refresh_logout_flow(existing_user) -> None:
    client = APIClient()

    login_response = client.post(
        "/api/v1/auth/login/",
        {"email": "integration.user@example.com", "password": "correct-horse-battery-staple"},
        format="json",
    )
    tokens = login_response.data["data"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")
    me_response = client.get("/api/v1/auth/me/")
    assert me_response.status_code == 200
    assert me_response.data["data"]["email"] == "integration.user@example.com"

    refresh_response = client.post(
        "/api/v1/auth/token/refresh/", {"refresh_token": tokens["refresh_token"]}, format="json"
    )
    assert refresh_response.status_code == 200
    new_tokens = refresh_response.data["data"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # The rotated-out refresh token must no longer work.
    replay_response = client.post(
        "/api/v1/auth/token/refresh/", {"refresh_token": tokens["refresh_token"]}, format="json"
    )
    assert replay_response.status_code == 401

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_tokens['access_token']}")
    logout_response = client.post(
        "/api/v1/auth/logout/", {"refresh_token": new_tokens["refresh_token"]}, format="json"
    )
    assert logout_response.status_code == 200

    # The access token used to log out must itself now be revoked.
    post_logout_me = client.get("/api/v1/auth/me/")
    assert post_logout_me.status_code == 401
