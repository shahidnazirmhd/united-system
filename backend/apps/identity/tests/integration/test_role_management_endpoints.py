"""Integration tests for role management and role assignment — verifies
RBAC is actually enforced end-to-end (a caller without identity.manage_roles
gets 403), not just that the use cases behave correctly in isolation.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.identity.infrastructure.models import (
    PermissionRecord,
    RoleRecord,
    UserRecord,
)
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher

pytestmark = pytest.mark.django_db


def _login(client: APIClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login/", {"email": email, "password": password}, format="json")
    return response.data["data"]["access_token"]


@pytest.fixture
def hasher() -> DjangoPasswordHasher:
    return DjangoPasswordHasher()


@pytest.fixture
def manage_roles_permission() -> PermissionRecord:
    # Seeded by apps/identity/migrations/0002_seed_system_roles.py, not
    # created here — that migration already runs once when the test
    # database is built, so a second PermissionRecord with this same code
    # would collide with the seeded row (code is unique). Fetch it instead
    # of creating a duplicate.
    return PermissionRecord.objects.get(code="identity.manage_roles")


@pytest.fixture
def admin_user(hasher, manage_roles_permission) -> UserRecord:
    user = UserRecord.objects.create(email="admin@example.com", password_hash=hasher.hash("admin-password-123"))
    # "HR Admin" is seeded by 0002_seed_system_roles.py with every identity.*
    # permission (including manage_roles_permission above) already granted —
    # fetch it rather than creating a second role with the same name.
    admin_role = RoleRecord.objects.get(name="HR Admin")
    user.roles.add(admin_role, through_defaults={"assigned_by": None})
    return user


@pytest.fixture
def plain_user(hasher) -> UserRecord:
    return UserRecord.objects.create(email="employee@example.com", password_hash=hasher.hash("employee-pass-123"))


def test_role_creation_requires_manage_roles_permission(plain_user) -> None:
    client = APIClient()
    token = _login(client, "employee@example.com", "employee-pass-123")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = client.post("/api/v1/auth/roles/", {"name": "New Role"}, format="json")

    assert response.status_code == 403


def test_admin_can_create_role_and_assign_it(admin_user, plain_user) -> None:
    client = APIClient()
    token = _login(client, "admin@example.com", "admin-password-123")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    create_response = client.post("/api/v1/auth/roles/", {"name": "Auditor"}, format="json")
    assert create_response.status_code == 201
    role_id = create_response.data["data"]["id"]

    assign_response = client.post(
        f"/api/v1/auth/users/{plain_user.id}/roles/", {"role_id": role_id}, format="json"
    )
    assert assign_response.status_code == 200

    # Assigning the same role twice is a conflict, not a silent success.
    duplicate_response = client.post(
        f"/api/v1/auth/users/{plain_user.id}/roles/", {"role_id": role_id}, format="json"
    )
    assert duplicate_response.status_code == 409

    revoke_response = client.delete(f"/api/v1/auth/users/{plain_user.id}/roles/{role_id}/")
    assert revoke_response.status_code == 200
