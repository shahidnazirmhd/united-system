"""Integration tests for the Employee endpoints — real Postgres, exercising
the full stack from HTTP down to the database, including a real JWT login
against Identity to prove the two modules actually interoperate through
`employees.manage_employees`/`employees.view_employees` (seeded by
apps/employees/migrations/0002_seed_employee_permissions.py onto the HR
Admin role seeded by apps/identity/migrations/0002_seed_system_roles.py).
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.employees.infrastructure.models import DepartmentRecord
from apps.identity.infrastructure.models import RoleRecord, UserRecord, UserRoleRecord
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher

pytestmark = pytest.mark.django_db

_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def department():
    # "ENG" is seeded by apps/employees/migrations/0003_seed_default_departments.py,
    # which runs once when the test database is built — not per test. Creating
    # a second DepartmentRecord with the same code here would collide with
    # that seeded row (code is unique), so fetch it instead.
    return DepartmentRecord.objects.get(code="ENG")


@pytest.fixture
def hr_admin_client():
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(
        email="hr.admin@example.com", password_hash=hasher.hash(_PASSWORD)
    )
    # Seeded by identity's 0002 migration as "HR Admin", renamed to "Admin" by
    # 0006_rename_admin_role_and_prune_system_roles.py (Role & Permission
    # Management phase) — both migrations have already run by the time the
    # test database is built.
    hr_admin_role = RoleRecord.objects.get(name="Admin")
    UserRoleRecord.objects.create(user=user, role=hr_admin_role)

    client = APIClient()
    login_response = client.post(
        "/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json"
    )
    assert login_response.status_code == 200, login_response.data
    access_token = login_response.data["data"]["access_token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


def _create_payload(department_id, **overrides):
    payload = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "work_email": "ada.lovelace@example.com",
        "department_id": str(department_id),
        "job_title": "Software Engineer",
        "employment_type": "full_time",
        "date_of_joining": "2024-01-15",
    }
    payload.update(overrides)
    return payload


def test_create_employee_requires_authentication(department) -> None:
    client = APIClient()

    response = client.post("/api/v1/employees/", _create_payload(department.id), format="json")

    assert response.status_code == 401


def test_create_employee_succeeds_for_hr_admin(hr_admin_client, department) -> None:
    response = hr_admin_client.post(
        "/api/v1/employees/", _create_payload(department.id), format="json"
    )

    assert response.status_code == 201, response.data
    assert response.data["data"]["employee_code"].startswith("EMP-")
    assert response.data["data"]["status"] == "active"
    assert response.data["data"]["full_name"] == "Ada Lovelace"


def test_create_employee_rejects_duplicate_work_email(hr_admin_client, department) -> None:
    hr_admin_client.post("/api/v1/employees/", _create_payload(department.id), format="json")

    response = hr_admin_client.post("/api/v1/employees/", _create_payload(department.id), format="json")

    assert response.status_code == 409
    assert response.data["error"]["code"] == "duplicate_work_email"


def test_create_employee_rejects_unknown_department(hr_admin_client) -> None:
    import uuid

    response = hr_admin_client.post(
        "/api/v1/employees/", _create_payload(uuid.uuid4()), format="json"
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "department_not_found"


def test_full_employee_lifecycle(hr_admin_client, department) -> None:
    create_response = hr_admin_client.post(
        "/api/v1/employees/", _create_payload(department.id), format="json"
    )
    employee_id = create_response.data["data"]["id"]

    get_response = hr_admin_client.get(f"/api/v1/employees/{employee_id}/")
    assert get_response.status_code == 200
    assert get_response.data["data"]["id"] == employee_id

    list_response = hr_admin_client.get("/api/v1/employees/")
    assert list_response.status_code == 200
    assert list_response.data["meta"]["total_count"] == 1

    search_response = hr_admin_client.get("/api/v1/employees/search/", {"q": "Lovelace"})
    assert search_response.status_code == 200
    assert search_response.data["meta"]["total_count"] == 1

    deactivate_response = hr_admin_client.post(f"/api/v1/employees/{employee_id}/deactivate/")
    assert deactivate_response.status_code == 200
    assert deactivate_response.data["data"]["status"] == "suspended"

    activate_response = hr_admin_client.post(f"/api/v1/employees/{employee_id}/activate/")
    assert activate_response.status_code == 200
    assert activate_response.data["data"]["status"] == "active"

    update_response = hr_admin_client.patch(
        f"/api/v1/employees/{employee_id}/",
        _create_payload(department.id, job_title="Principal Engineer"),
        format="json",
    )
    assert update_response.status_code == 200
    assert update_response.data["data"]["job_title"] == "Principal Engineer"


# --- Self-service /me (Phase 7) -----------------------------------------
# Proves the least-privilege gap fix: an employee with no
# employees.view_employees grant — just some ordinary role with zero
# permissions (see the `zero_permission_role` fixture in the rootdir
# conftest.py) — can still see their own record, and only their own.


@pytest.fixture
def employee_self_service_client(department, zero_permission_role):
    """A logged-in User with no employees.* permission at all, linked to a
    real EmployeeRecord via the reciprocal user_id/employee_id pair — the
    same shape Telegram auto-provisioning produces."""
    from apps.employees.infrastructure.models import EmployeeRecord

    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="ada.self@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)

    employee_record = EmployeeRecord.objects.create(
        employee_code="EMP-000042",
        user_id=user.id,
        first_name="Ada",
        last_name="Lovelace",
        work_email="ada.lovelace.self@example.com",
        department=department,
        job_title="Software Engineer",
        employment_type="full_time",
        date_of_joining="2024-01-15",
    )

    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    assert login_response.status_code == 200, login_response.data
    access_token = login_response.data["data"]["access_token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, employee_record


def test_me_requires_authentication() -> None:
    client = APIClient()

    response = client.get("/api/v1/employees/me/")

    assert response.status_code == 401


def test_me_returns_own_profile_without_view_employees_permission(employee_self_service_client) -> None:
    client, employee_record = employee_self_service_client

    response = client.get("/api/v1/employees/me/")

    assert response.status_code == 200, response.data
    assert response.data["data"]["id"] == str(employee_record.id)
    assert response.data["data"]["full_name"] == "Ada Lovelace"
    assert response.data["data"]["department_name"] == "Engineering"


def test_me_rejects_plain_get_employee_by_id_without_permission(employee_self_service_client) -> None:
    """The baseline Employee role must still be denied the general-purpose
    detail endpoint — /me/ is a narrow carve-out, not a blanket grant."""
    client, employee_record = employee_self_service_client

    response = client.get(f"/api/v1/employees/{employee_record.id}/")

    assert response.status_code == 403


def test_me_returns_not_found_when_user_has_no_linked_employee(zero_permission_role) -> None:
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="unlinked.user@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)

    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    access_token = login_response.data["data"]["access_token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    response = client.get("/api/v1/employees/me/")

    assert response.status_code == 404
    assert response.data["error"]["code"] == "employee_not_found"
