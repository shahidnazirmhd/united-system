"""Integration tests for the Leave endpoints — real Postgres, exercising the
full stack from HTTP down to the database, including a real JWT login
against Identity and a real linked Employee record (same shape
apps/employees/tests/integration/test_employee_endpoints.py's
`employee_self_service_client` fixture already established for `/employees/me/`).

Requires a real Postgres database and the project's dependencies installed
— cannot be executed inside the sandbox this module was authored in (no
network/pip access there); syntax-verified via `ast.parse` and cross-checked
field-by-field against `interface/urls.py`/`interface/serializers.py`
instead. Run for real per TESTING_GUIDE.md.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.employees.infrastructure.models import DepartmentRecord, EmployeeRecord
from apps.identity.infrastructure.models import RoleRecord, UserRecord, UserRoleRecord
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher
from apps.leave.infrastructure.models import LeaveBalanceRecord, LeaveTypeRecord

pytestmark = pytest.mark.django_db

_PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def department():
    return DepartmentRecord.objects.get(code="ENG")


@pytest.fixture
def annual_leave_type():
    # Seeded by apps/leave/migrations/0003_seed_default_leave_types.py.
    return LeaveTypeRecord.objects.get(code="ANNUAL")


@pytest.fixture
def employee_client(department):
    """A logged-in User with no leave.* permission at all, linked to a real
    EmployeeRecord — the baseline shape every self-service test below uses."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="grace.self@example.com", password_hash=hasher.hash(_PASSWORD))
    employee_role = RoleRecord.objects.get(name="Employee")  # zero permissions
    UserRoleRecord.objects.create(user=user, role=employee_role)

    employee_record = EmployeeRecord.objects.create(
        employee_code="EMP-000099",
        user_id=user.id,
        first_name="Grace",
        last_name="Hopper",
        work_email="grace.hopper.self@example.com",
        department=department,
        job_title="Rear Admiral",
        employment_type="full_time",
        date_of_joining="2020-01-15",
    )

    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    assert login_response.status_code == 200, login_response.data
    access_token = login_response.data["data"]["access_token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client, employee_record


@pytest.fixture
def hr_admin_client():
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="hr.admin.leave@example.com", password_hash=hasher.hash(_PASSWORD))
    hr_admin_role = RoleRecord.objects.get(name="HR Admin")
    UserRoleRecord.objects.create(user=user, role=hr_admin_role)

    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    assert login_response.status_code == 200, login_response.data
    access_token = login_response.data["data"]["access_token"]
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    return client


def _future_range(start_offset_days=30, length_days=3):
    start = date.today() + timedelta(days=start_offset_days)
    end = start + timedelta(days=length_days - 1)
    return start, end


# --- Leave Types ----------------------------------------------------------


def test_list_leave_types_requires_authentication() -> None:
    client = APIClient()

    response = client.get("/api/v1/leave/types/")

    assert response.status_code == 401


def test_list_leave_types_returns_seeded_types(employee_client) -> None:
    client, _employee = employee_client

    response = client.get("/api/v1/leave/types/")

    assert response.status_code == 200
    codes = {t["code"] for t in response.data["data"]}
    assert {"ANNUAL", "SICK", "UNPAID"}.issubset(codes)


# --- Leave Balance ----------------------------------------------------------


def test_my_balance_reflects_auto_provisioned_row_from_employee_creation(employee_client, annual_leave_type) -> None:
    """EmployeeRecord created via ORM directly (not through the API) does
    NOT publish EmployeeCreated, so balances are zeroed here by design —
    proves the "zero entitlement, not a 404" fallback (see
    LeaveBalanceService.get_balance's docstring)."""
    client, _employee = employee_client

    response = client.get("/api/v1/leave/balance/me/")

    assert response.status_code == 200
    annual = next(b for b in response.data["data"] if b["leave_type_id"] == str(annual_leave_type.id))
    assert annual["entitled_days"] == "0.00"


def test_my_balance_reflects_entitlement_after_provisioning(employee_client, annual_leave_type) -> None:
    client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year, entitled_days="20.00"
    )

    response = client.get("/api/v1/leave/balance/me/")

    annual = next(b for b in response.data["data"] if b["leave_type_id"] == str(annual_leave_type.id))
    assert annual["entitled_days"] == "20.00"
    assert annual["available_days"] == "20.00"


def test_employee_balance_endpoint_requires_view_leave_permission(employee_client) -> None:
    client, employee = employee_client

    response = client.get(f"/api/v1/leave/balance/{employee.id}/")

    assert response.status_code == 403


def test_hr_admin_can_view_any_employees_balance(hr_admin_client, employee_client) -> None:
    _self_client, employee = employee_client

    response = hr_admin_client.get(f"/api/v1/leave/balance/{employee.id}/")

    assert response.status_code == 200


# --- Apply Leave ----------------------------------------------------------


def test_apply_leave_succeeds_with_sufficient_balance(employee_client, annual_leave_type) -> None:
    client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    start, end = _future_range()
    start, end = date(start.year + 1, start.month, start.day), date(end.year + 1, end.month, end.day)

    response = client.post(
        "/api/v1/leave/requests/",
        {
            "leave_type_id": str(annual_leave_type.id),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "reason": "Family trip",
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    assert response.data["data"]["status"] == "pending"
    assert response.data["data"]["total_days"] == "3.00"


def test_apply_leave_rejects_insufficient_balance(employee_client, annual_leave_type) -> None:
    client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="1.00"
    )
    start, end = date(date.today().year + 1, 6, 1), date(date.today().year + 1, 6, 5)

    response = client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )

    assert response.status_code == 422
    assert response.data["error"]["code"] == "insufficient_leave_balance"


def test_apply_leave_rejects_unknown_leave_type(employee_client) -> None:
    client, _employee = employee_client
    start, end = _future_range()

    response = client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(uuid.uuid4()), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "leave_type_not_found"


def test_apply_leave_rejects_overlapping_request(employee_client, annual_leave_type) -> None:
    client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="30.00"
    )
    start, end = date(date.today().year + 1, 6, 1), date(date.today().year + 1, 6, 5)
    client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )

    response = client.post(
        "/api/v1/leave/requests/",
        {
            "leave_type_id": str(annual_leave_type.id),
            "start_date": date(date.today().year + 1, 6, 4).isoformat(),
            "end_date": date(date.today().year + 1, 6, 8).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 422
    assert response.data["error"]["code"] == "overlapping_leave_request"


# --- View History / Details / Cancel ---------------------------------------


def test_full_leave_request_lifecycle(employee_client, annual_leave_type) -> None:
    client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    start, end = date(date.today().year + 1, 7, 1), date(date.today().year + 1, 7, 3)

    create_response = client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )
    request_id = create_response.data["data"]["id"]

    detail_response = client.get(f"/api/v1/leave/requests/{request_id}/")
    assert detail_response.status_code == 200
    assert detail_response.data["data"]["id"] == request_id

    history_response = client.get("/api/v1/leave/requests/")
    assert history_response.status_code == 200
    assert history_response.data["meta"]["total_count"] == 1

    cancel_response = client.post(
        f"/api/v1/leave/requests/{request_id}/cancel/", {"cancellation_reason": "No longer needed"}, format="json"
    )
    assert cancel_response.status_code == 200
    assert cancel_response.data["data"]["status"] == "cancelled"


def test_cannot_view_another_employees_leave_request_without_permission(employee_client, annual_leave_type) -> None:
    client_a, employee_a = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee_a.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    start, end = date(date.today().year + 1, 8, 1), date(date.today().year + 1, 8, 2)
    create_response = client_a.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )
    request_id = create_response.data["data"]["id"]

    hasher = DjangoPasswordHasher()
    user_b = UserRecord.objects.create(email="employee.b@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user_b, role=RoleRecord.objects.get(name="Employee"))
    EmployeeRecord.objects.create(
        employee_code="EMP-000100",
        user_id=user_b.id,
        first_name="Bob",
        last_name="Employee",
        work_email="bob.employee@example.com",
        department=DepartmentRecord.objects.get(code="ENG"),
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2024-01-01",
    )
    client_b = APIClient()
    login_response = client_b.post("/api/v1/auth/login/", {"email": user_b.email, "password": _PASSWORD}, format="json")
    client_b.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access_token']}")

    response = client_b.get(f"/api/v1/leave/requests/{request_id}/")

    assert response.status_code == 422
    assert response.data["error"]["code"] == "leave_request_ownership_mismatch"


# --- Telegram Gateway-facing surface -----------------------------------


def test_telegram_endpoints_reject_missing_internal_service_key(employee_client) -> None:
    client = APIClient()

    response = client.get("/api/v1/leave/telegram/types/")

    assert response.status_code == 403
