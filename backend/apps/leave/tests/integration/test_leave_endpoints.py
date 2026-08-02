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
from datetime import date, datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from apps.employees.infrastructure.models import DepartmentRecord, EmployeeRecord
from apps.identity.infrastructure.models import (
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    UserRecord,
    UserRoleRecord,
)
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher
from apps.leave.infrastructure.models import LeaveBalanceRecord, LeaveTypeRecord

# Approval Engine (Phase 9): Apply Leave now requires the applicant to have
# a manager who is linked to Telegram (see
# LeaveValidationService.validate_manager_available_for_approval) — every
# fixture below that exercises apply_leave creates one.
_NEXT_TELEGRAM_USER_ID = iter(range(900_000_001, 900_999_999))


def _create_linked_manager(department, *, employee_code: str) -> EmployeeRecord:
    return EmployeeRecord.objects.create(
        employee_code=employee_code,
        first_name="Manager",
        last_name="Approver",
        work_email=f"{employee_code.lower()}@example.com",
        department=department,
        job_title="Engineering Manager",
        employment_type="full_time",
        date_of_joining="2018-01-01",
        telegram_user_id=next(_NEXT_TELEGRAM_USER_ID),
        telegram_chat_id=next(_NEXT_TELEGRAM_USER_ID),
        telegram_username="manager_on_telegram",
        telegram_linked_at=datetime.now(timezone.utc),
    )


def _create_linked_manager_with_login(department, *, employee_code: str, zero_permission_role) -> tuple[EmployeeRecord, APIClient]:
    """Phase 13: the HR review requirement needs a manager who can actually
    decide their level-1 approval step over HTTP (not just via Telegram),
    to prove level 1 approving does NOT finalize the leave by itself
    anymore — `_create_linked_manager` above only sets up Telegram linkage,
    with no Identity User at all, since Phase 9's tests never needed the
    manager to log in."""
    manager = _create_linked_manager(department, employee_code=employee_code)
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(
        email=f"{employee_code.lower()}@example.com", password_hash=hasher.hash(_PASSWORD)
    )
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    manager.user_id = user.id
    manager.save(update_fields=["user_id"])
    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    assert login_response.status_code == 200, login_response.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access_token']}")
    return manager, client


pytestmark = pytest.mark.django_db

_PASSWORD = "correct-horse-battery-staple"
# Approval Workflow Changes review round — mirrors
# apps/employees/tests/integration/test_employee_telegram_endpoints.py's
# exact internal-service-key fixture/header pattern, needed here now that
# the manager's level-1 leave approval decision must go through the
# Telegram-facing surface instead of the web JWT one.
_SERVICE_KEY = "test-internal-service-key"
_HEADER = "HTTP_X_INTERNAL_SERVICE_KEY"


@pytest.fixture(autouse=True)
def internal_service_key(settings):
    settings.INTERNAL_SERVICE_API_KEY = _SERVICE_KEY


def _telegram_client() -> APIClient:
    client = APIClient()
    client.credentials(**{_HEADER: _SERVICE_KEY})
    return client


@pytest.fixture
def department():
    return DepartmentRecord.objects.get(code="ENG")


@pytest.fixture
def annual_leave_type():
    # Seeded by apps/leave/migrations/0003_seed_default_leave_types.py.
    return LeaveTypeRecord.objects.get(code="ANNUAL")


@pytest.fixture
def employee_client(department, zero_permission_role):
    """A logged-in User with no leave.* permission at all, linked to a real
    EmployeeRecord — the baseline shape every self-service test below uses."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="grace.self@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)

    manager_record = _create_linked_manager(department, employee_code="EMP-MGR-000099")
    employee_record = EmployeeRecord.objects.create(
        employee_code="EMP-000099",
        user_id=user.id,
        first_name="Grace",
        last_name="Hopper",
        work_email="grace.hopper.self@example.com",
        department=department,
        manager=manager_record,
        job_title="Rear Admiral",
        employment_type="full_time",
        date_of_joining="2020-01-15",
        # Round 14 item 6: current_status defaults to "not_joined", which is
        # NOT eligible to apply for leave — this fixture represents an
        # already-active employee (self-service leave application is the
        # baseline shape every test below uses), so it must be "working".
        current_status="working",
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
    # Seeded as "HR Admin" by identity's 0002 migration, renamed to "Admin" by
    # 0006_rename_admin_role_and_prune_system_roles.py.
    hr_admin_role = RoleRecord.objects.get(name="Admin")
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


def test_my_balance_is_an_empty_list_not_a_404_for_a_caller_with_no_employee_record(zero_permission_role) -> None:
    """Empty-state review requirement: a pure Admin/HR account with no
    linked EmployeeRecord has zero balance rows — `GET /leave/balance/me/`
    must return `200 []`, not `404 employee_not_found`, or the frontend
    renders "Couldn't load, try again" for what is really just "no data
    yet." See `LeaveService.resolve_employee_id_for_user_or_none`."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="admin.no.employee.bal@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    assert login_response.status_code == 200, login_response.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access_token']}")

    response = client.get("/api/v1/leave/balance/me/")

    assert response.status_code == 200
    assert response.data["data"] == []


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


# --- Approval Engine (Phase 9) integration --------------------------------


def test_apply_leave_rejects_when_no_manager_assigned(department, annual_leave_type, zero_permission_role) -> None:
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="no.manager@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    employee = EmployeeRecord.objects.create(
        employee_code="EMP-000101",
        user_id=user.id,
        first_name="No",
        last_name="Manager",
        work_email="no.manager.emp@example.com",
        department=department,
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2024-01-01",
        # manager deliberately left unset
        current_status="working",  # round 14 item 6 — see employee_client's identical comment
    )
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access_token']}")
    start, end = date(date.today().year + 1, 6, 1), date(date.today().year + 1, 6, 3)

    response = client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )

    assert response.status_code == 422
    assert response.data["error"]["code"] == "no_manager_assigned"


def test_apply_leave_rejects_when_manager_not_linked_to_telegram(
    department, annual_leave_type, zero_permission_role
) -> None:
    unlinked_manager = EmployeeRecord.objects.create(
        employee_code="EMP-MGR-000102",
        first_name="Unlinked",
        last_name="Manager",
        work_email="unlinked.manager@example.com",
        department=department,
        job_title="Engineering Manager",
        employment_type="full_time",
        date_of_joining="2018-01-01",
        # no telegram_user_id set
    )
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(
        email="manager.not.linked@example.com", password_hash=hasher.hash(_PASSWORD)
    )
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    employee = EmployeeRecord.objects.create(
        employee_code="EMP-000102",
        user_id=user.id,
        first_name="Has",
        last_name="UnlinkedManager",
        work_email="has.unlinked.manager@example.com",
        department=department,
        manager=unlinked_manager,
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2024-01-01",
        current_status="working",  # round 14 item 6 — see employee_client's identical comment
    )
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access_token']}")
    start, end = date(date.today().year + 1, 6, 1), date(date.today().year + 1, 6, 3)

    response = client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )

    assert response.status_code == 422
    assert response.data["error"]["code"] == "manager_not_linked_to_telegram"


def test_apply_leave_opens_an_approval_request_for_the_manager(employee_client, annual_leave_type) -> None:
    """End-to-end proof of the Leave <-> Approvals wiring: applying for
    leave creates a real `ApprovalRequestRecord`/`ApprovalStepRecord` pair,
    level 1, assigned to the applicant's manager — not just a `LeaveRequest`
    row."""
    from apps.approvals.infrastructure.models import ApprovalRequestRecord

    client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    start, end = date(date.today().year + 1, 6, 1), date(date.today().year + 1, 6, 3)

    response = client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )
    assert response.status_code == 201, response.data
    leave_request_id = response.data["data"]["id"]

    approval_request = ApprovalRequestRecord.objects.get(
        subject_type="leave.leave_request", subject_id=leave_request_id
    )
    assert approval_request.status == "pending"
    assert approval_request.current_level == 1
    assert approval_request.requested_by_employee_id == employee.id
    step = approval_request.steps.get(level=1)
    assert str(step.approver_employee_id) == str(employee.manager_id)
    assert step.status == "pending"


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


def test_my_leave_history_is_an_empty_page_not_a_404_for_a_caller_with_no_employee_record(
    zero_permission_role,
) -> None:
    """Empty-state review requirement: a pure Admin/HR account with no
    linked EmployeeRecord has zero leave requests of their own —
    `GET /leave/requests/` must return a `200` empty page (`total_count: 0`),
    not `404 employee_not_found`. See
    `LeaveService.resolve_employee_id_for_user_or_none`."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="admin.no.employee.hist@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    client = APIClient()
    login_response = client.post("/api/v1/auth/login/", {"email": user.email, "password": _PASSWORD}, format="json")
    assert login_response.status_code == 200, login_response.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access_token']}")

    response = client.get("/api/v1/leave/requests/")

    assert response.status_code == 200
    assert response.data["data"] == []
    assert response.data["meta"]["total_count"] == 0
    assert response.data["meta"]["total_pages"] == 1


def test_cannot_view_another_employees_leave_request_without_permission(
    employee_client, annual_leave_type, zero_permission_role
) -> None:
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
    UserRoleRecord.objects.create(user=user_b, role=zero_permission_role)
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


# --- Phase 13: Leave Type Management ---------------------------------------


def test_manage_leave_types_requires_manage_leave_permission(employee_client) -> None:
    client, _employee = employee_client

    response = client.get("/api/v1/leave/types/manage/")

    assert response.status_code == 403


def test_hr_admin_can_create_and_update_a_leave_type(hr_admin_client) -> None:
    create_response = hr_admin_client.post(
        "/api/v1/leave/types/manage/",
        {"name": "Compassionate Leave", "code": "COMPASSIONATE", "default_annual_days": "5.00"},
        format="json",
    )
    assert create_response.status_code == 201, create_response.data
    leave_type_id = create_response.data["data"]["id"]

    update_response = hr_admin_client.patch(
        f"/api/v1/leave/types/manage/{leave_type_id}/",
        {
            "name": "Compassionate Leave",
            "code": "COMPASSIONATE",
            "default_annual_days": "7.00",
            "is_paid": True,
            "requires_approval": True,
            "is_active": False,
        },
        format="json",
    )
    assert update_response.status_code == 200, update_response.data
    assert update_response.data["data"]["default_annual_days"] == "7.00"
    assert update_response.data["data"]["is_active"] is False


def test_hr_admin_cannot_create_a_leave_type_with_a_duplicate_code(hr_admin_client, annual_leave_type) -> None:
    response = hr_admin_client.post(
        "/api/v1/leave/types/manage/",
        {"name": "Another Annual", "code": annual_leave_type.code, "default_annual_days": "5.00"},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "duplicate_leave_type_code"


def test_manage_leave_types_list_includes_inactive_rows(hr_admin_client) -> None:
    hr_admin_client.post(
        "/api/v1/leave/types/manage/",
        {"name": "Study Leave", "code": "STUDY", "default_annual_days": "3.00"},
        format="json",
    )
    leave_type_id = hr_admin_client.get("/api/v1/leave/types/manage/?search=Study").data["data"][0]["id"]
    hr_admin_client.patch(
        f"/api/v1/leave/types/manage/{leave_type_id}/",
        {
            "name": "Study Leave",
            "code": "STUDY",
            "default_annual_days": "3.00",
            "is_paid": True,
            "requires_approval": True,
            "is_active": False,
        },
        format="json",
    )

    response = hr_admin_client.get("/api/v1/leave/types/manage/?is_active=false")

    assert response.status_code == 200
    assert "STUDY" in {t["code"] for t in response.data["data"]}


# --- Phase 13: Apply/Cancel leave on behalf of an employee -----------------


def test_apply_leave_for_employee_requires_manage_leave_permission(employee_client, annual_leave_type) -> None:
    client, employee = employee_client
    start, end = _future_range()

    response = client.post(
        f"/api/v1/leave/requests/employee/{employee.id}/apply/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )

    assert response.status_code == 403


def test_hr_admin_can_apply_leave_on_behalf_of_an_employee(hr_admin_client, employee_client, annual_leave_type) -> None:
    """Proves the on-behalf endpoint uses the exact same approval workflow
    (Phase 13 requirement) — the resulting ApprovalRequest's
    requested_by_employee_id is the employee, never the HR caller."""
    from apps.approvals.infrastructure.models import ApprovalRequestRecord

    _self_client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    start, end = date(date.today().year + 1, 9, 1), date(date.today().year + 1, 9, 3)

    response = hr_admin_client.post(
        f"/api/v1/leave/requests/employee/{employee.id}/apply/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert response.data["data"]["employee_id"] == str(employee.id)
    approval_request = ApprovalRequestRecord.objects.get(
        subject_type="leave.leave_request", subject_id=response.data["data"]["id"]
    )
    assert approval_request.requested_by_employee_id == employee.id


def test_hr_admin_can_cancel_any_employees_leave_request(hr_admin_client, employee_client, annual_leave_type) -> None:
    client, employee = employee_client
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    start, end = date(date.today().year + 1, 9, 10), date(date.today().year + 1, 9, 12)
    create_response = client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )
    request_id = create_response.data["data"]["id"]

    response = hr_admin_client.post(
        f"/api/v1/leave/requests/{request_id}/cancel-for-employee/",
        {"cancellation_reason": "HR-initiated cancellation"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["status"] == "cancelled"


# --- Phase 13: Leave Balance Adjustment / Opening ---------------------------


def test_adjust_balance_requires_manage_leave_permission(employee_client, annual_leave_type) -> None:
    client, employee = employee_client

    response = client.post(
        "/api/v1/leave/balances/adjust/",
        {
            "employee_id": str(employee.id),
            "leave_type_id": str(annual_leave_type.id),
            "year": date.today().year,
            "entitled_days": "20.00",
            "used_days": "0.00",
            "carried_forward_days": "0.00",
            "reason": "Should be rejected",
        },
        format="json",
    )

    assert response.status_code == 403


def test_hr_admin_can_open_a_new_balance_row(hr_admin_client, employee_client, annual_leave_type) -> None:
    _self_client, employee = employee_client
    year = date.today().year + 2  # a year with no existing balance row

    response = hr_admin_client.post(
        "/api/v1/leave/balances/adjust/",
        {
            "employee_id": str(employee.id),
            "leave_type_id": str(annual_leave_type.id),
            "year": year,
            "entitled_days": "22.00",
            "used_days": "0.00",
            "carried_forward_days": "3.00",
            "reason": "Opening entitlement for the new year",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["adjustment_type"] == "opening"
    assert response.data["data"]["new_entitled_days"] == "22.00"


def test_hr_admin_can_adjust_an_existing_balance_row(hr_admin_client, employee_client, annual_leave_type) -> None:
    _self_client, employee = employee_client
    year = date.today().year
    LeaveBalanceRecord.objects.create(
        employee_id=employee.id, leave_type=annual_leave_type, year=year, entitled_days="20.00"
    )

    response = hr_admin_client.post(
        "/api/v1/leave/balances/adjust/",
        {
            "employee_id": str(employee.id),
            "leave_type_id": str(annual_leave_type.id),
            "year": year,
            "entitled_days": "25.00",
            "used_days": "0.00",
            "carried_forward_days": "0.00",
            "reason": "Correcting a data-entry error",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["adjustment_type"] == "adjustment"
    assert response.data["data"]["previous_entitled_days"] == "20.00"
    assert response.data["data"]["new_entitled_days"] == "25.00"


# --- Phase 13 (review requirement): two-stage approval before finalization -


def test_leave_is_not_finalized_until_hr_admin_also_approves(
    department, zero_permission_role, annual_leave_type
) -> None:
    """The core review-requirement proof: a manager approving via Telegram
    must NOT finalize the leave by itself anymore — only once an HR/Admin
    (anyone holding `approvals.level2_approve`, not one designated person)
    also approves, from the web HR system (the ONLY channel level 2 may be
    decided from), does the request become APPROVED, the balance get
    debited, and "fully processed" become true.

    Approval Workflow Changes v2: level 1 is no longer Telegram-only — the
    manager here deliberately does NOT hold `approvals.level1_approve`
    (linked only via `zero_permission_role`), so their web decide attempt
    is rejected on IDENTITY/PERMISSION grounds (`not_the_assigned_approver`)
    rather than a channel restriction; a separate test below proves a
    non-manager `approvals.level1_approve` holder CAN complete level 1 from
    the web instead. Level 2 is unchanged — still web-only, so HR/Admin's
    Telegram attempt is still rejected with `approval_channel_not_allowed`."""
    from apps.approvals.infrastructure.models import ApprovalRequestRecord

    hasher = DjangoPasswordHasher()

    manager, manager_client = _create_linked_manager_with_login(
        department, employee_code="EMP-MGR-REVIEW-001", zero_permission_role=zero_permission_role
    )

    applicant_user = UserRecord.objects.create(
        email="applicant.review@example.com", password_hash=hasher.hash(_PASSWORD)
    )
    UserRoleRecord.objects.create(user=applicant_user, role=zero_permission_role)
    applicant = EmployeeRecord.objects.create(
        employee_code="EMP-APPLICANT-RVW-01",
        user_id=applicant_user.id,
        first_name="Ana",
        last_name="Applicant",
        work_email="ana.applicant@example.com",
        department=department,
        manager=manager,
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2021-01-01",
        current_status="working",  # round 14 item 6 — see employee_client's identical comment
    )
    LeaveBalanceRecord.objects.create(
        employee_id=applicant.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    applicant_client = APIClient()
    applicant_login = applicant_client.post(
        "/api/v1/auth/login/", {"email": applicant_user.email, "password": _PASSWORD}, format="json"
    )
    assert applicant_login.status_code == 200, applicant_login.data
    applicant_client.credentials(HTTP_AUTHORIZATION=f"Bearer {applicant_login.data['data']['access_token']}")

    hr_role, _ = RoleRecord.objects.get_or_create(
        name="Test Level2 Approve Role",
        defaults={"description": "Test-only role granting approvals.level2_approve."},
    )
    level2_approve_permission = PermissionRecord.objects.get(code="approvals.level2_approve")
    RolePermissionRecord.objects.get_or_create(role=hr_role, permission=level2_approve_permission)
    hr_user = UserRecord.objects.create(email="hr.reviewer@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=hr_user, role=hr_role)
    hr_employee = EmployeeRecord.objects.create(
        employee_code="EMP-HRREVIEW-001",
        user_id=hr_user.id,
        first_name="Helen",
        last_name="Reviewer",
        work_email="helen.reviewer.leave@example.com",
        department=department,
        job_title="HR Business Partner",
        employment_type="full_time",
        date_of_joining="2019-01-01",
        # Deliberately ALSO linked to Telegram — proves "level 2 must be
        # completed from the HR system" is a real restriction, not just an
        # accident of Helen never having a telegram_user_id to try it with.
        telegram_user_id=920_000_001,
        telegram_chat_id=920_000_002,
        telegram_username="helen_on_telegram",
        telegram_linked_at=datetime.now(timezone.utc),
    )
    # Mirror what `handle_employee_created`/`handle_employee_linked_to_user`
    # would set in production (see `apps/identity/interface/event_handlers.py`)
    # — this test creates the Employee directly via the ORM, bypassing the
    # real event publication, so `UserRecord.employee_id` (the field
    # `GetPermissionCodesForEmployeeUseCase` resolves Helen's permission
    # grants through) must be set explicitly or her level-2 decide below
    # would 403 as "not the assigned approver".
    UserRecord.objects.filter(id=hr_user.id).update(employee_id=hr_employee.id)
    hr_client = APIClient()
    hr_login = hr_client.post("/api/v1/auth/login/", {"email": hr_user.email, "password": _PASSWORD}, format="json")
    assert hr_login.status_code == 200, hr_login.data
    hr_client.credentials(HTTP_AUTHORIZATION=f"Bearer {hr_login.data['data']['access_token']}")

    start, end = date(date.today().year + 1, 6, 1), date(date.today().year + 1, 6, 3)
    apply_response = applicant_client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )
    assert apply_response.status_code == 201, apply_response.data
    leave_request_id = apply_response.data["data"]["id"]

    approval_request = ApprovalRequestRecord.objects.get(
        subject_type="leave.leave_request", subject_id=leave_request_id
    )

    # --- Manager cannot approve level 1 from the web HR system — they are
    # not the manager identity-check needed for Telegram, and they don't
    # hold `approvals.level1_approve` needed for the web. ------------------
    manager_web_attempt = manager_client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "approve"}, format="json"
    )
    assert manager_web_attempt.status_code == 403, manager_web_attempt.data
    assert manager_web_attempt.data["error"]["code"] == "not_the_assigned_approver"

    # --- Manager approves (level 1) via Telegram — must NOT finalize. ----
    manager_decision = _telegram_client().post(
        "/api/v1/approvals/telegram/decide/",
        {
            "telegram_user_id": manager.telegram_user_id,
            "approval_request_id": str(approval_request.id),
            "decision": "approve",
        },
        format="json",
    )
    assert manager_decision.status_code == 200, manager_decision.data
    assert manager_decision.data["data"]["status"] == "pending"
    assert manager_decision.data["data"]["current_level"] == 2

    still_pending = applicant_client.get(f"/api/v1/leave/requests/{leave_request_id}/")
    assert still_pending.data["data"]["status"] == "pending"
    balance_after_manager = applicant_client.get(
        f"/api/v1/leave/balance/me/?year={date.today().year + 1}"
    )
    row_after_manager = next(
        b for b in balance_after_manager.data["data"] if b["leave_type_id"] == str(annual_leave_type.id)
    )
    assert row_after_manager["used_days"] == "0.00"

    # --- HR/Admin cannot approve level 2 from Telegram, even though Helen
    # is linked there too. ---------------------------------------------
    hr_telegram_attempt = _telegram_client().post(
        "/api/v1/approvals/telegram/decide/",
        {
            "telegram_user_id": hr_employee.telegram_user_id,
            "approval_request_id": str(approval_request.id),
            "decision": "approve",
        },
        format="json",
    )
    assert hr_telegram_attempt.status_code == 403, hr_telegram_attempt.data
    assert hr_telegram_attempt.data["error"]["code"] == "approval_channel_not_allowed"

    # --- HR/Admin approves (level 2) from the web HR system — NOW it
    # finalizes. ----------------------------------------------------------
    hr_decision = hr_client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/",
        {"decision": "approve", "comments": "All good"},
        format="json",
    )
    assert hr_decision.status_code == 200, hr_decision.data
    assert hr_decision.data["data"]["status"] == "approved"

    finalized = applicant_client.get(f"/api/v1/leave/requests/{leave_request_id}/")
    assert finalized.data["data"]["status"] == "approved"
    balance_after_hr = applicant_client.get(f"/api/v1/leave/balance/me/?year={date.today().year + 1}")
    row_after_hr = next(
        b for b in balance_after_hr.data["data"] if b["leave_type_id"] == str(annual_leave_type.id)
    )
    assert row_after_hr["used_days"] == "3.00"


def test_level1_approval_can_be_completed_from_the_web_by_a_non_manager_permission_holder(
    department, zero_permission_role, annual_leave_type
) -> None:
    """Approval Workflow Changes v2: 'HR system Level 1 approval must be
    controlled by role permissions... only users with Level 1 approval
    permission can approve Level 1 from the HR system.' Proves the
    positive case end-to-end through Leave's REAL chain resolver: someone
    who is NOT the applicant's manager, but holds `approvals.level1_approve`,
    completes level 1 from the web HR system — and the response shows THAT
    person's name/code, not the manager's, once decided."""
    hasher = DjangoPasswordHasher()

    manager = _create_linked_manager(department, employee_code="EMP-MGR-L1WEB-001")

    applicant_user = UserRecord.objects.create(
        email="applicant.l1web@example.com", password_hash=hasher.hash(_PASSWORD)
    )
    UserRoleRecord.objects.create(user=applicant_user, role=zero_permission_role)
    applicant = EmployeeRecord.objects.create(
        employee_code="EMP-APP-L1WEB-01",
        user_id=applicant_user.id,
        first_name="Amir",
        last_name="Applicant",
        work_email="amir.applicant@example.com",
        department=department,
        manager=manager,
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2021-01-01",
        current_status="working",  # round 14 item 6 — see employee_client's identical comment
    )
    LeaveBalanceRecord.objects.create(
        employee_id=applicant.id, leave_type=annual_leave_type, year=date.today().year + 1, entitled_days="20.00"
    )
    applicant_client = APIClient()
    applicant_login = applicant_client.post(
        "/api/v1/auth/login/", {"email": applicant_user.email, "password": _PASSWORD}, format="json"
    )
    assert applicant_login.status_code == 200, applicant_login.data
    applicant_client.credentials(HTTP_AUTHORIZATION=f"Bearer {applicant_login.data['data']['access_token']}")

    level1_role, _ = RoleRecord.objects.get_or_create(
        name="Test Level1 Approve Role", defaults={"description": "Test-only role granting approvals.level1_approve."}
    )
    level1_approve_permission = PermissionRecord.objects.get(code="approvals.level1_approve")
    RolePermissionRecord.objects.get_or_create(role=level1_role, permission=level1_approve_permission)
    backup_user = UserRecord.objects.create(email="backup.l1web@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=backup_user, role=level1_role)
    backup_employee = EmployeeRecord.objects.create(
        employee_code="EMP-BACKUPL1-001",
        user_id=backup_user.id,
        first_name="Beth",
        last_name="BackupApprover",
        work_email="beth.backupapprover@example.com",
        department=department,
        job_title="Senior Manager",
        employment_type="full_time",
        date_of_joining="2017-01-01",
    )
    UserRecord.objects.filter(id=backup_user.id).update(employee_id=backup_employee.id)
    backup_client = APIClient()
    backup_login = backup_client.post(
        "/api/v1/auth/login/", {"email": backup_user.email, "password": _PASSWORD}, format="json"
    )
    assert backup_login.status_code == 200, backup_login.data
    backup_client.credentials(HTTP_AUTHORIZATION=f"Bearer {backup_login.data['data']['access_token']}")

    from apps.approvals.infrastructure.models import ApprovalRequestRecord

    start, end = date(date.today().year + 1, 7, 1), date(date.today().year + 1, 7, 2)
    apply_response = applicant_client.post(
        "/api/v1/leave/requests/",
        {"leave_type_id": str(annual_leave_type.id), "start_date": start.isoformat(), "end_date": end.isoformat()},
        format="json",
    )
    assert apply_response.status_code == 201, apply_response.data
    approval_request = ApprovalRequestRecord.objects.get(
        subject_type="leave.leave_request", subject_id=apply_response.data["data"]["id"]
    )

    response = backup_client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/",
        {"decision": "approve", "comments": "Covering for the manager"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["status"] == "pending"  # advances to level 2, doesn't finalize
    assert response.data["data"]["current_level"] == 2
    assert response.data["data"]["steps"][0]["approver_employee_name"] == "Beth BackupApprover"
    assert response.data["data"]["steps"][0]["approver_employee_code"] == "EMP-BACKUPL1-001"


# --- Phase 13 (review requirement): HR-wide "manage" leave request list ----


def test_manage_leave_requests_requires_view_leave_permission(employee_client) -> None:
    client, _employee = employee_client

    response = client.get("/api/v1/leave/requests/manage/")

    assert response.status_code == 403


def test_hr_admin_can_list_leave_requests_across_every_employee(
    hr_admin_client, employee_client, annual_leave_type
) -> None:
    _self_client, employee = employee_client
    start, end = date(date.today().year + 1, 9, 1), date(date.today().year + 1, 9, 2)
    from apps.leave.infrastructure.models import LeaveRequestRecord

    LeaveRequestRecord.objects.create(
        employee_id=employee.id,
        leave_type=annual_leave_type,
        start_date=start,
        end_date=end,
        total_days="2.00",
        status="pending",
    )

    response = hr_admin_client.get("/api/v1/leave/requests/manage/")

    assert response.status_code == 200, response.data
    assert response.data["meta"]["total_count"] >= 1
    row = next(r for r in response.data["data"] if r["employee_id"] == str(employee.id))
    assert row["employee_name"] == f"{employee.first_name} {employee.last_name}"
    assert row["employee_code"] == employee.employee_code


def test_manage_leave_requests_filters_by_employee_id(
    hr_admin_client, employee_client, annual_leave_type
) -> None:
    _self_client, employee = employee_client
    start, end = date(date.today().year + 1, 10, 1), date(date.today().year + 1, 10, 2)
    from apps.leave.infrastructure.models import LeaveRequestRecord

    LeaveRequestRecord.objects.create(
        employee_id=employee.id,
        leave_type=annual_leave_type,
        start_date=start,
        end_date=end,
        total_days="2.00",
        status="pending",
    )

    response = hr_admin_client.get(f"/api/v1/leave/requests/manage/?employee_id={employee.id}")

    assert response.status_code == 200, response.data
    assert all(r["employee_id"] == str(employee.id) for r in response.data["data"])
    assert response.data["meta"]["total_count"] == 1


def test_hr_admin_with_no_linked_employee_can_view_another_employees_leave_request_detail(
    hr_admin_client, employee_client, annual_leave_type
) -> None:
    """Round 16 item 2 regression test: `hr_admin_client` is a pure Admin
    User with NO linked EmployeeRecord (the exact shape reported — "GET
    /leave/requests/{id}/ -> 404"). Detail used to be gated by the RAISING
    `resolve_employee_id_for_user`, which raised `LeaveEmployeeNotFoundError`
    (404) for any caller with no employee id of their own, even one holding
    `leave.view_leave` — indistinguishable in the response from "this leave
    request doesn't exist." `_ensure_can_view` now takes an
    Optional[caller_employee_id] and skips straight to the permission check
    for a caller with none. This is also what unblocked the HR web Leave
    Request Detail page (previously "Couldn't load") and, downstream, ever
    seeing the manager's approval decision on it."""
    _self_client, employee = employee_client
    start, end = date(date.today().year + 1, 11, 1), date(date.today().year + 1, 11, 2)
    from apps.leave.infrastructure.models import LeaveRequestRecord

    leave_request = LeaveRequestRecord.objects.create(
        employee_id=employee.id,
        leave_type=annual_leave_type,
        start_date=start,
        end_date=end,
        total_days="2.00",
        working_days="2.00",
        status="pending",
    )

    response = hr_admin_client.get(f"/api/v1/leave/requests/{leave_request.id}/")

    assert response.status_code == 200, response.data
    assert response.data["data"]["id"] == str(leave_request.id)
    assert response.data["data"]["employee_id"] == str(employee.id)


def test_employee_without_view_leave_permission_cannot_view_a_different_employees_leave_request(
    employee_client, annual_leave_type
) -> None:
    """The other half of `_ensure_can_view`'s contract, unaffected by the
    round 16 item 2 fix above: a caller who IS linked to an employee record
    but neither owns this request nor holds `leave.view_leave` still gets
    the ownership-mismatch error, not a free pass."""
    client, _employee = employee_client
    other_employee_id = uuid.uuid4()
    start, end = date(date.today().year + 1, 11, 5), date(date.today().year + 1, 11, 6)
    from apps.leave.infrastructure.models import LeaveRequestRecord

    other_leave_request = LeaveRequestRecord.objects.create(
        employee_id=other_employee_id,
        leave_type=annual_leave_type,
        start_date=start,
        end_date=end,
        total_days="2.00",
        working_days="2.00",
        status="pending",
    )

    response = client.get(f"/api/v1/leave/requests/{other_leave_request.id}/")

    assert response.status_code == 422, response.data
    assert response.data["error"]["code"] == "leave_request_ownership_mismatch"
