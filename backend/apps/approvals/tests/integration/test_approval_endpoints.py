"""Integration tests for the Approval Engine's own REST endpoints — real
Postgres, exercising the full stack from HTTP down to the database.

Deliberately exercises the generic engine in isolation from any subject
module: `ApprovalRequestRecord`/`ApprovalStepRecord` rows are created
directly via the ORM (as if some subject module — Leave or a future one —
had already called `ApprovalService.create_approval_request`), rather than
going through `apps.leave`'s `/api/v1/leave/requests/` endpoint. The
Leave <-> Approvals wiring itself is covered by
`apps/leave/tests/integration/test_leave_endpoints.py`'s
`test_apply_leave_opens_an_approval_request_for_the_manager`.

Requires a real Postgres database — cannot be executed inside the sandbox
this module was authored in (no network/pip access there); syntax-verified
via `ast.parse` and cross-checked field-by-field against
`interface/urls.py`/`interface/serializers.py` instead. Run for real per
TESTING_GUIDE.md.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from rest_framework.test import APIClient

from apps.approvals.infrastructure.models import ApprovalRequestRecord, ApprovalStepRecord
from apps.employees.infrastructure.models import DepartmentRecord, EmployeeRecord
from apps.identity.infrastructure.models import (
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    UserRecord,
    UserRoleRecord,
)
from apps.identity.infrastructure.password_hasher import DjangoPasswordHasher

pytestmark = pytest.mark.django_db

_PASSWORD = "correct-horse-battery-staple"
_SUBJECT_TYPE = "leave.leave_request"
# Approval Workflow Changes review round — mirrors
# apps/employees/tests/integration/test_employee_telegram_endpoints.py's
# exact internal-service-key fixture/header pattern for the Telegram-facing
# surface's `HasInternalServiceKey` permission.
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


def _login(email: str) -> APIClient:
    client = APIClient()
    response = client.post("/api/v1/auth/login/", {"email": email, "password": _PASSWORD}, format="json")
    assert response.status_code == 200, response.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['data']['access_token']}")
    return client


@pytest.fixture
def approver_client(department, zero_permission_role):
    """A logged-in User linked to a real EmployeeRecord — the manager who
    will be the assigned approver on the approval requests below."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="approver@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    employee = EmployeeRecord.objects.create(
        employee_code="EAPPROVER-001",
        user_id=user.id,
        first_name="Ada",
        last_name="Approver",
        work_email="ada.approver@example.com",
        department=department,
        job_title="Engineering Manager",
        employment_type="full_time",
        date_of_joining="2018-01-01",
    )
    return _login(user.email), employee


@pytest.fixture
def manage_leave_client(department):
    """A logged-in User with a real custom role granting `leave.manage_leave`
    AND (Approval Workflow Changes v2) `approvals.level2_approve`, linked to
    a real EmployeeRecord — proves permission-based approval steps
    (`apps.approvals.domain.value_objects.ApproverAssignment.for_permission`)
    really resolve through a real Identity role/permission grant, not just
    through the generic engine's own unit-test fakes (see
    `test_approval_service.py`'s `FakeAuthorizationPort` for that half of
    the coverage). Both permissions are granted because tests using this
    fixture exercise the REAL `leave.leave_request` subject_type end to end
    (`_open_approval_request`/`_open_permission_based_level_2` both default
    to it), so approving level 1 triggers Leave's real chain resolver,
    which now gates level 2 by `approvals.level2_approve` specifically —
    `leave.manage_leave` alone is kept too since some of this file's own
    tests still pass it explicitly as a step's `approver_permission_code`
    to exercise the generic engine in isolation from Leave's real codes."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="hr.manage.leave@example.com", password_hash=hasher.hash(_PASSWORD))
    role, _ = RoleRecord.objects.get_or_create(
        name="Test Leave Manager Role",
        defaults={"description": "Test-only role granting leave.manage_leave and approvals.level2_approve."},
    )
    for code in ("leave.manage_leave", "approvals.level2_approve"):
        permission = PermissionRecord.objects.get(code=code)
        RolePermissionRecord.objects.get_or_create(role=role, permission=permission)
    UserRoleRecord.objects.create(user=user, role=role)
    employee = EmployeeRecord.objects.create(
        employee_code="EHRMANAGE-001",
        user_id=user.id,
        first_name="Helen",
        last_name="Reviewer",
        work_email="helen.reviewer@example.com",
        department=department,
        job_title="HR Business Partner",
        employment_type="full_time",
        date_of_joining="2019-01-01",
    )
    # In production, `UserRecord.employee_id` (Identity's own mirror of the
    # Employee<->User link, distinct from `EmployeeRecord.user_id` above) is
    # only populated by `handle_employee_created`/`handle_employee_linked_to_user`
    # reacting to the real `EmployeeCreated`/`EmployeeLinkedToUser` domain
    # events — this fixture creates the Employee directly via the ORM, so
    # those events never fire. `GetPermissionCodesForEmployeeUseCase` (used
    # by `ApprovalService.decide`/`list_pending_for_approver` to resolve a
    # permission-based step) looks Helen up by `employee_id`, so without this
    # explicit mirror her permission grants would never resolve.
    UserRecord.objects.filter(id=user.id).update(employee_id=employee.id)
    return _login(user.email), employee


def _open_permission_based_level_2(*, requester_employee_id, permission_code="leave.manage_leave") -> ApprovalRequestRecord:
    """A request already past a (fictitious, already-approved) level 1,
    now sitting at a permission-based level 2 — mirrors exactly what
    `LeaveApprovalChainResolver` produces once a manager approves a real
    leave request."""
    request = ApprovalRequestRecord.objects.create(
        subject_type=_SUBJECT_TYPE,
        subject_id=uuid.uuid4(),
        requested_by_employee_id=requester_employee_id,
        subject_summary="Annual Leave: 2026-09-01 -> 2026-09-03 (3 days)",
        current_level=2,
    )
    ApprovalStepRecord.objects.create(
        approval_request=request, level=1, approver_employee_id=uuid.uuid4(), status="approved"
    )
    ApprovalStepRecord.objects.create(approval_request=request, level=2, approver_permission_code=permission_code)
    return request


@pytest.fixture
def requester_employee(department):
    return EmployeeRecord.objects.create(
        employee_code="EREQUESTER-001",
        first_name="Rita",
        last_name="Requester",
        work_email="rita.requester@example.com",
        department=department,
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2022-01-01",
    )


def _open_approval_request(
    *,
    approver_employee_id,
    requester_employee_id,
    subject_id=None,
    restricted_to_channel=None,
    approver_permission_code=None,
    permission_required_for_channel=None,
) -> ApprovalRequestRecord:
    request = ApprovalRequestRecord.objects.create(
        subject_type=_SUBJECT_TYPE,
        subject_id=subject_id or uuid.uuid4(),
        requested_by_employee_id=requester_employee_id,
        subject_summary="Annual Leave: 2026-09-01 -> 2026-09-03 (3 days)",
    )
    ApprovalStepRecord.objects.create(
        approval_request=request,
        level=1,
        approver_employee_id=approver_employee_id,
        restricted_to_channel=restricted_to_channel,
        # Approval Workflow Changes v2 — dual-mode, only set by the tests
        # that need it (see "decide: dual-mode approver" section below).
        approver_permission_code=approver_permission_code,
        permission_required_for_channel=permission_required_for_channel,
    )
    return request


@pytest.fixture
def channel_restricted_approver_client(department, zero_permission_role):
    """Approval Workflow Changes review round: like `approver_client`, but
    ALSO linked to Telegram — proves the generic channel-restriction
    mechanism itself (not anything Leave-specific) by giving one employee
    both a web login and a `telegram_user_id`, so the same person can be
    used to prove "wrong channel, right person" from either direction."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="channel.approver@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    employee = EmployeeRecord.objects.create(
        employee_code="ECHANAPPR-001",
        user_id=user.id,
        first_name="Cara",
        last_name="ChannelApprover",
        work_email="cara.channelapprover@example.com",
        department=department,
        job_title="Engineering Manager",
        employment_type="full_time",
        date_of_joining="2018-01-01",
        telegram_user_id=910_000_001,
        telegram_chat_id=910_000_002,
        telegram_username="cara_on_telegram",
        telegram_linked_at=datetime.now(timezone.utc),
    )
    return _login(user.email), employee


@pytest.fixture
def dual_mode_manager_client(department, zero_permission_role):
    """Approval Workflow Changes v2: a manager who is Telegram-linked but
    does NOT hold `approvals.level1_approve` — proves the web channel of a
    dual-mode step is governed purely by the permission, not by being this
    employee, while Telegram remains governed by identity alone."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="dual.manager@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    employee = EmployeeRecord.objects.create(
        employee_code="EDUALMGR-001",
        user_id=user.id,
        first_name="Mona",
        last_name="Manager",
        work_email="mona.manager@example.com",
        department=department,
        job_title="Engineering Manager",
        employment_type="full_time",
        date_of_joining="2018-01-01",
        telegram_user_id=930_000_001,
        telegram_chat_id=930_000_002,
        telegram_username="mona_on_telegram",
        telegram_linked_at=datetime.now(timezone.utc),
    )
    return _login(user.email), employee


@pytest.fixture
def level1_approve_client(department):
    """A logged-in User with a real custom role granting the new
    `approvals.level1_approve` permission — deliberately NOT Telegram-linked
    and NOT the manager referenced on a dual-mode step, proving the web
    channel is decidable by ANY holder of the permission, not just whoever
    was originally referenced."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="level1.approver@example.com", password_hash=hasher.hash(_PASSWORD))
    role, _ = RoleRecord.objects.get_or_create(
        name="Test Level1 Approve Role", defaults={"description": "Test-only role granting approvals.level1_approve."}
    )
    permission = PermissionRecord.objects.get(code="approvals.level1_approve")
    RolePermissionRecord.objects.get_or_create(role=role, permission=permission)
    UserRoleRecord.objects.create(user=user, role=role)
    employee = EmployeeRecord.objects.create(
        employee_code="ELVL1APPR-001",
        user_id=user.id,
        first_name="Leo",
        last_name="Level1Approver",
        work_email="leo.level1approver@example.com",
        department=department,
        job_title="HR Business Partner",
        employment_type="full_time",
        date_of_joining="2019-01-01",
    )
    UserRecord.objects.filter(id=user.id).update(employee_id=employee.id)
    return _login(user.email), employee


@pytest.fixture
def telegram_linked_level1_approve_client(department):
    """Holds `approvals.level1_approve` AND is Telegram-linked, but is not
    the manager referenced on a dual-mode step — proves Telegram decisions
    are governed by identity alone, ignoring the permission entirely."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(
        email="telegram.level1.approver@example.com", password_hash=hasher.hash(_PASSWORD)
    )
    role, _ = RoleRecord.objects.get_or_create(
        name="Test Level1 Approve Role", defaults={"description": "Test-only role granting approvals.level1_approve."}
    )
    permission = PermissionRecord.objects.get(code="approvals.level1_approve")
    RolePermissionRecord.objects.get_or_create(role=role, permission=permission)
    UserRoleRecord.objects.create(user=user, role=role)
    employee = EmployeeRecord.objects.create(
        employee_code="ETGLVL1-001",
        user_id=user.id,
        first_name="Tara",
        last_name="TelegramLevel1",
        work_email="tara.telegramlevel1@example.com",
        department=department,
        job_title="HR Business Partner",
        employment_type="full_time",
        date_of_joining="2019-01-01",
        telegram_user_id=940_000_001,
        telegram_chat_id=940_000_002,
        telegram_username="tara_on_telegram",
        telegram_linked_at=datetime.now(timezone.utc),
    )
    UserRecord.objects.filter(id=user.id).update(employee_id=employee.id)
    return _login(user.email), employee


# --- pending/me -------------------------------------------------------


def test_my_pending_approvals_requires_authentication() -> None:
    client = APIClient()

    response = client.get("/api/v1/approvals/pending/me/")

    assert response.status_code == 401


def test_my_pending_approvals_lists_only_my_assigned_steps(approver_client, requester_employee) -> None:
    client, approver = approver_client
    _open_approval_request(approver_employee_id=approver.id, requester_employee_id=requester_employee.id)

    response = client.get("/api/v1/approvals/pending/me/")

    assert response.status_code == 200
    assert len(response.data["data"]) == 1
    item = response.data["data"][0]
    assert item["current_level"] == 1
    assert item["status"] == "pending"
    assert item["steps"][0]["approver_employee_id"] == str(approver.id)
    # Approval Workflow Changes review round: a `for_employee` step's
    # response is enriched with the approver's real display name/code
    # (resolved via `EmployeeLookupPort`), not just their opaque id — this
    # is what lets the HR system show "Pending — Ada Approver
    # (EAPPROVER-001)" for a Telegram-only level like Leave's manager
    # step, without ever calling the decide endpoint from the web.
    assert item["steps"][0]["approver_employee_name"] == "Ada Approver"
    assert item["steps"][0]["approver_employee_code"] == "EAPPROVER-001"


def test_my_pending_approvals_is_empty_when_nothing_is_assigned(approver_client) -> None:
    client, _approver = approver_client

    response = client.get("/api/v1/approvals/pending/me/")

    assert response.status_code == 200
    assert response.data["data"] == []


def test_my_pending_approvals_is_an_empty_list_not_a_404_for_a_caller_with_no_employee_record(
    zero_permission_role,
) -> None:
    """Empty-state review requirement: a pure Admin/HR account with no
    linked EmployeeRecord (created directly via Identity, never through the
    Employee module) has zero pending approvals — the endpoint must return
    `200 []`, not `404 employee_not_found`, or the frontend renders
    "Couldn't load, try again" for what is really just "no data yet."""
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="admin.no.employee@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    client = _login(user.email)

    response = client.get("/api/v1/approvals/pending/me/")

    assert response.status_code == 200
    assert response.data["data"] == []


# --- decide -----------------------------------------------------------


def test_approve_marks_request_approved_and_records_comments(
    approver_client, manage_leave_client, requester_employee
) -> None:
    """`_open_approval_request` reuses `_SUBJECT_TYPE = "leave.leave_request"`
    — the exact subject_type Leave's own, real `LeaveApprovalChainResolver`
    is registered under (see that class's docstring) — so a level-1 approve
    here advances to a real level-2 permission-based step (any
    `leave.manage_leave` holder) instead of finalizing immediately; only the
    level-2 decision actually completes the chain. This test therefore
    decides both levels before asserting `approved`."""
    client, approver = approver_client
    approval_request = _open_approval_request(
        approver_employee_id=approver.id, requester_employee_id=requester_employee.id
    )

    level_1_response = client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/",
        {"decision": "approve", "comments": "Approved by manager"},
        format="json",
    )
    assert level_1_response.status_code == 200, level_1_response.data
    assert level_1_response.data["data"]["status"] == "pending"
    assert level_1_response.data["data"]["current_level"] == 2

    hr_client, _hr_employee = manage_leave_client
    response = hr_client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/",
        {"decision": "approve", "comments": "Approved, enjoy your trip"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["status"] == "approved"
    assert response.data["data"]["steps"][0]["comments"] == "Approved by manager"
    assert response.data["data"]["steps"][1]["comments"] == "Approved, enjoy your trip"


def test_reject_marks_request_rejected(approver_client, requester_employee) -> None:
    client, approver = approver_client
    approval_request = _open_approval_request(
        approver_employee_id=approver.id, requester_employee_id=requester_employee.id
    )

    response = client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "reject"}, format="json"
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["status"] == "rejected"


def test_decide_rejects_a_caller_who_is_not_the_assigned_approver(
    department, requester_employee, zero_permission_role
) -> None:
    approval_request = _open_approval_request(
        approver_employee_id=uuid.uuid4(), requester_employee_id=requester_employee.id
    )
    hasher = DjangoPasswordHasher()
    user = UserRecord.objects.create(email="not.the.approver@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=user, role=zero_permission_role)
    EmployeeRecord.objects.create(
        employee_code="ENOTAPPROVER-001",
        user_id=user.id,
        first_name="Not",
        last_name="Approver",
        work_email="not.approver.emp@example.com",
        department=department,
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2023-01-01",
    )
    client = _login(user.email)

    response = client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "approve"}, format="json"
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "not_the_assigned_approver"


# --- decide: channel restriction (Approval Workflow Changes review) --------
# Generic proof at the real-HTTP level, independent of Leave — the request
# below is a plain, manually-constructed step with `restricted_to_channel`
# set directly, exactly as Leave's own `LeaveApprovalChainResolver` would
# produce for its level-1/level-2 assignments, but exercised here purely as
# a feature of the engine itself.


def test_decide_rejects_the_right_approver_on_the_wrong_channel(
    channel_restricted_approver_client, requester_employee
) -> None:
    web_client, approver = channel_restricted_approver_client
    approval_request = _open_approval_request(
        approver_employee_id=approver.id,
        requester_employee_id=requester_employee.id,
        restricted_to_channel="telegram",
    )

    response = web_client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "approve"}, format="json"
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "approval_channel_not_allowed"


def test_decide_succeeds_for_the_right_approver_on_the_matching_channel(
    channel_restricted_approver_client, requester_employee
) -> None:
    """`_open_approval_request` uses `_SUBJECT_TYPE = "leave.leave_request"`
    — the real subject_type Leave's own resolver is registered under — so
    approving this manually-constructed level-1 step advances to a real
    level-2 permission-based step (see
    `test_approve_marks_request_approved_and_records_comments`'s identical
    note) instead of finalizing immediately. The point of THIS test is only
    that the matching-channel decide call itself succeeds (`200`, not
    `403`), not that it single-handedly completes the whole chain."""
    _web_client, approver = channel_restricted_approver_client
    approval_request = _open_approval_request(
        approver_employee_id=approver.id,
        requester_employee_id=requester_employee.id,
        restricted_to_channel="telegram",
    )
    telegram_client = _telegram_client()

    response = telegram_client.post(
        "/api/v1/approvals/telegram/decide/",
        {
            "telegram_user_id": approver.telegram_user_id,
            "approval_request_id": str(approval_request.id),
            "decision": "approve",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["status"] == "pending"
    assert response.data["data"]["current_level"] == 2


def test_my_pending_approvals_web_excludes_a_telegram_restricted_step(
    channel_restricted_approver_client, requester_employee
) -> None:
    """The manager's web "My Pending Approvals" must not even show a step
    they could never successfully decide from there — "do not allow Level 1
    approval from the HR system" applies to visibility, not just the
    decide endpoint itself."""
    web_client, approver = channel_restricted_approver_client
    _open_approval_request(
        approver_employee_id=approver.id,
        requester_employee_id=requester_employee.id,
        restricted_to_channel="telegram",
    )

    response = web_client.get("/api/v1/approvals/pending/me/")

    assert response.status_code == 200
    assert response.data["data"] == []


def test_pending_approvals_telegram_includes_a_telegram_restricted_step(
    channel_restricted_approver_client, requester_employee
) -> None:
    _web_client, approver = channel_restricted_approver_client
    _open_approval_request(
        approver_employee_id=approver.id,
        requester_employee_id=requester_employee.id,
        restricted_to_channel="telegram",
    )
    telegram_client = _telegram_client()

    response = telegram_client.get(
        "/api/v1/approvals/telegram/pending/", {"telegram_user_id": approver.telegram_user_id}
    )

    assert response.status_code == 200
    assert len(response.data["data"]) == 1


# --- decide: dual-mode approver (Approval Workflow Changes v2) ------------
# Generic proof at the real-HTTP level, independent of Leave, that a step
# assigned via `ApproverAssignment.for_employee_or_permission_by_channel`
# (both an employee id AND a permission code) is governed by identity on
# every channel EXCEPT the one named, and by the permission on that one —
# exactly what Leave's real level 1 now uses (manager via Telegram,
# `approvals.level1_approve` via the web).


def test_decide_dual_mode_web_rejects_the_manager_without_the_level1_permission(
    dual_mode_manager_client, requester_employee
) -> None:
    web_client, manager = dual_mode_manager_client
    approval_request = _open_approval_request(
        approver_employee_id=manager.id,
        requester_employee_id=requester_employee.id,
        approver_permission_code="approvals.level1_approve",
        permission_required_for_channel="web",
    )

    response = web_client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "approve"}, format="json"
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "not_the_assigned_approver"


def test_decide_dual_mode_web_succeeds_for_a_non_manager_holding_the_permission(
    dual_mode_manager_client, level1_approve_client, requester_employee
) -> None:
    _manager_client, manager = dual_mode_manager_client
    approve_client, _approve_employee = level1_approve_client
    approval_request = _open_approval_request(
        approver_employee_id=manager.id,
        requester_employee_id=requester_employee.id,
        approver_permission_code="approvals.level1_approve",
        permission_required_for_channel="web",
    )

    response = approve_client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/",
        {"decision": "approve", "comments": "Approved from HR system"},
        format="json",
    )

    assert response.status_code == 200, response.data
    # Real leave.leave_request subject_type — advances to a real level 2,
    # same as the plain single-mode `test_approve_marks_request_approved...`
    # test above, since apps.leave's real resolver is registered for it.
    assert response.data["data"]["status"] == "pending"
    assert response.data["data"]["current_level"] == 2
    # Approval Workflow Changes v2: the actual decider's name is shown, not
    # the originally-referenced manager's.
    assert response.data["data"]["steps"][0]["approver_employee_name"] == "Leo Level1Approver"
    assert response.data["data"]["steps"][0]["approver_employee_code"] == "ELVL1APPR-001"


def test_decide_dual_mode_telegram_rejects_a_permission_holder_who_is_not_the_manager(
    telegram_linked_level1_approve_client, requester_employee
) -> None:
    _client, approve_employee = telegram_linked_level1_approve_client
    approval_request = _open_approval_request(
        approver_employee_id=uuid.uuid4(),  # some other, unrelated "manager"
        requester_employee_id=requester_employee.id,
        approver_permission_code="approvals.level1_approve",
        permission_required_for_channel="web",
    )
    telegram_client = _telegram_client()

    response = telegram_client.post(
        "/api/v1/approvals/telegram/decide/",
        {
            "telegram_user_id": approve_employee.telegram_user_id,
            "approval_request_id": str(approval_request.id),
            "decision": "approve",
        },
        format="json",
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "not_the_assigned_approver"


def test_decide_dual_mode_telegram_succeeds_for_the_manager_regardless_of_permission(
    dual_mode_manager_client, requester_employee
) -> None:
    _web_client, manager = dual_mode_manager_client
    approval_request = _open_approval_request(
        approver_employee_id=manager.id,
        requester_employee_id=requester_employee.id,
        approver_permission_code="approvals.level1_approve",
        permission_required_for_channel="web",
    )
    telegram_client = _telegram_client()

    response = telegram_client.post(
        "/api/v1/approvals/telegram/decide/",
        {
            "telegram_user_id": manager.telegram_user_id,
            "approval_request_id": str(approval_request.id),
            "decision": "approve",
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["status"] == "pending"
    assert response.data["data"]["current_level"] == 2


def test_decide_twice_returns_conflict_the_second_time(
    approver_client, manage_leave_client, requester_employee
) -> None:
    """Same two-level subject_type as the test above — the request must be
    decided through BOTH levels (manager, then any leave.manage_leave
    holder) before it's terminal; only a decide attempt AFTER that should
    hit `approval_request_not_pending`."""
    client, approver = approver_client
    approval_request = _open_approval_request(
        approver_employee_id=approver.id, requester_employee_id=requester_employee.id
    )
    client.post(f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "approve"}, format="json")
    hr_client, _hr_employee = manage_leave_client
    hr_client.post(f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "approve"}, format="json")

    response = client.post(f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "reject"}, format="json")

    assert response.status_code == 409
    assert response.data["error"]["code"] == "approval_request_not_pending"


# --- decide: permission-based levels (Phase 13 — Leave's HR/Admin level) ---


def test_permission_based_step_can_be_decided_by_any_employee_holding_the_permission(
    manage_leave_client, requester_employee
) -> None:
    """Real end-to-end proof (real Postgres, real Identity role/permission
    grant) that `ApproverAssignment.for_permission` steps are decidable by
    ANY employee holding that permission, not one designated person —
    exercises the full `IdentityAuthorizationAdapter` ->
    `GetPermissionCodesForEmployeeUseCase` -> `UserRepository.get_by_employee_id`
    chain, which `test_approval_service.py`'s unit tests fake out entirely."""
    client, _hr_employee = manage_leave_client
    approval_request = _open_permission_based_level_2(requester_employee_id=requester_employee.id)

    response = client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/",
        {"decision": "approve", "comments": "Reviewed and approved"},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["status"] == "approved"
    assert response.data["data"]["steps"][1]["comments"] == "Reviewed and approved"


def test_permission_based_step_rejects_an_employee_without_the_permission(
    approver_client, requester_employee
) -> None:
    """`approver_client` holds `zero_permission_role` — no `leave.manage_leave`
    — so it must not be able to decide a level assigned by that permission,
    even though it's a perfectly real, employee-linked, authenticated
    caller."""
    client, _approver = approver_client
    approval_request = _open_permission_based_level_2(requester_employee_id=requester_employee.id)

    response = client.post(
        f"/api/v1/approvals/{approval_request.id}/decide/", {"decision": "approve"}, format="json"
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "not_the_assigned_approver"


def test_my_pending_approvals_includes_permission_based_steps_the_caller_qualifies_for(
    manage_leave_client, requester_employee
) -> None:
    client, _hr_employee = manage_leave_client
    _open_permission_based_level_2(requester_employee_id=requester_employee.id)

    response = client.get("/api/v1/approvals/pending/me/")

    assert response.status_code == 200
    assert len(response.data["data"]) == 1
    assert response.data["data"][0]["steps"][0]["approver_permission_code"] == "leave.manage_leave"
    assert response.data["data"][0]["steps"][0]["approver_employee_id"] is None


# --- Phase 13: approval history by subject ---------------------------------


def test_approval_history_by_subject_visible_to_the_approver(approver_client, requester_employee) -> None:
    client, approver = approver_client
    subject_id = uuid.uuid4()
    _open_approval_request(
        approver_employee_id=approver.id, requester_employee_id=requester_employee.id, subject_id=subject_id
    )

    response = client.get(f"/api/v1/approvals/subject/{_SUBJECT_TYPE}/{subject_id}/")

    assert response.status_code == 200
    assert len(response.data["data"]) == 1
    assert response.data["data"][0]["subject_id"] == str(subject_id)


def test_approval_history_by_subject_hidden_from_an_unrelated_employee(
    approver_client, requester_employee, department, zero_permission_role
) -> None:
    _client, approver = approver_client
    subject_id = uuid.uuid4()
    _open_approval_request(
        approver_employee_id=approver.id, requester_employee_id=requester_employee.id, subject_id=subject_id
    )
    hasher = DjangoPasswordHasher()
    unrelated_user = UserRecord.objects.create(email="unrelated@example.com", password_hash=hasher.hash(_PASSWORD))
    UserRoleRecord.objects.create(user=unrelated_user, role=zero_permission_role)
    EmployeeRecord.objects.create(
        employee_code="EUNRELATED-001",
        user_id=unrelated_user.id,
        first_name="Uma",
        last_name="Unrelated",
        work_email="uma.unrelated@example.com",
        department=department,
        job_title="Engineer",
        employment_type="full_time",
        date_of_joining="2023-01-01",
    )
    unrelated_client = _login(unrelated_user.email)

    response = unrelated_client.get(f"/api/v1/approvals/subject/{_SUBJECT_TYPE}/{subject_id}/")

    assert response.status_code == 200
    assert response.data["data"] == []


def test_approval_history_by_subject_returns_empty_list_when_none_exist(approver_client) -> None:
    client, _approver = approver_client

    response = client.get(f"/api/v1/approvals/subject/{_SUBJECT_TYPE}/{uuid.uuid4()}/")

    assert response.status_code == 200
    assert response.data["data"] == []


# --- Telegram Gateway-facing surface -----------------------------------


def test_telegram_endpoints_reject_missing_internal_service_key() -> None:
    client = APIClient()

    response = client.get("/api/v1/approvals/telegram/pending/", {"telegram_user_id": 123456})

    assert response.status_code == 403
