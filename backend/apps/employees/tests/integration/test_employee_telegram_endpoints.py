"""Integration tests for the Employee module's Telegram-linking endpoints —
real Postgres, exercising the full stack from HTTP down to the database.

Every endpoint under test is Gateway-facing only (HasInternalServiceKey),
never employee-JWT-facing — see interface/telegram_views.py's module
docstring. `settings.INTERNAL_SERVICE_API_KEY` is set via pytest-django's
`settings` fixture (auto-restored after each test) rather than a real .env
value, keeping these tests independent of local configuration.

The OTP is recovered by monkeypatching `dependencies._build_email_client`
to a small in-memory recorder, not by scraping log output: the
`shared_kernel` logger tree sets `propagate=False`
(config/settings/base.py), so pytest's `caplog` — which attaches to the
root logger — would silently see nothing without extra, log-config-
specific wiring. Reading the message the code actually sent is more
direct and doesn't depend on logging configuration remaining as it is
today.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.employees.infrastructure.models import DepartmentRecord, EmployeeRecord
from apps.employees.interface import dependencies
from shared_kernel.infrastructure.email_client import EmailClientPort, EmailMessage

pytestmark = pytest.mark.django_db

_SERVICE_KEY = "test-internal-service-key"
_HEADER = "HTTP_X_INTERNAL_SERVICE_KEY"


class _RecordingEmailClient(EmailClientPort):
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture(autouse=True)
def internal_service_key(settings):
    settings.INTERNAL_SERVICE_API_KEY = _SERVICE_KEY


@pytest.fixture
def recording_email_client(monkeypatch):
    recorder = _RecordingEmailClient()
    monkeypatch.setattr(dependencies, "_build_email_client", lambda: recorder)
    return recorder


@pytest.fixture
def department():
    # "ENG" is seeded by apps/employees/migrations/0003_seed_default_departments.py,
    # which runs once when the test database is built — not per test. Creating
    # a second DepartmentRecord with the same code here would collide with
    # that seeded row (code is unique), so fetch it instead.
    return DepartmentRecord.objects.get(code="ENG")


@pytest.fixture
def employee(department):
    return EmployeeRecord.objects.create(
        employee_code="E000001",
        first_name="Grace",
        last_name="Hopper",
        work_email="grace.hopper@example.com",
        department=department,
        job_title="Rear Admiral",
        employment_type="full_time",
        date_of_joining="2000-01-01",
    )


@pytest.fixture
def gateway_client():
    client = APIClient()
    client.credentials(**{_HEADER: _SERVICE_KEY})
    return client


def _extract_otp(email_message: EmailMessage) -> str:
    # body_text ends "...is: {otp}\n\n..." — see infrastructure/otp_email_sender.py.
    marker = "is: "
    start = email_message.body_text.index(marker) + len(marker)
    return email_message.body_text[start : start + 6]


# --- HasInternalServiceKey enforcement -----------------------------------


def test_request_link_rejects_missing_service_key(employee) -> None:
    client = APIClient()

    response = client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 42, "chat_id": 42},
        format="json",
    )

    assert response.status_code == 403


def test_request_link_rejects_wrong_service_key(employee) -> None:
    client = APIClient()
    client.credentials(**{_HEADER: "not-the-right-key"})

    response = client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 42, "chat_id": 42},
        format="json",
    )

    assert response.status_code == 403


def test_profile_rejects_missing_service_key(employee) -> None:
    client = APIClient()

    response = client.get("/api/v1/employees/telegram/profile/", {"telegram_user_id": 42})

    assert response.status_code == 403


# --- Full linking lifecycle -----------------------------------------------


def test_full_telegram_linking_lifecycle(gateway_client, employee, recording_email_client) -> None:
    request_response = gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 4242, "chat_id": 4242},
        format="json",
    )
    assert request_response.status_code == 200, request_response.data
    assert len(recording_email_client.sent) == 1
    assert recording_email_client.sent[0].to_email == employee.work_email

    otp = _extract_otp(recording_email_client.sent[0])

    verify_response = gateway_client.post(
        "/api/v1/employees/telegram/link/verify/",
        {"telegram_user_id": 4242, "chat_id": 4242, "otp": otp, "telegram_username": "gracehopper"},
        format="json",
    )
    assert verify_response.status_code == 200, verify_response.data
    assert verify_response.data["data"]["is_linked_to_telegram"] is True
    assert verify_response.data["data"]["telegram_username"] == "gracehopper"

    status_response = gateway_client.get("/api/v1/employees/telegram/status/", {"telegram_user_id": 4242})
    assert status_response.status_code == 200
    assert status_response.data["data"]["is_linked"] is True

    profile_response = gateway_client.get("/api/v1/employees/telegram/profile/", {"telegram_user_id": 4242})
    assert profile_response.status_code == 200
    assert profile_response.data["data"]["employee_code"] == employee.employee_code
    assert profile_response.data["data"]["status"] == "active"

    unlink_response = gateway_client.post(
        "/api/v1/employees/telegram/unlink/", {"telegram_user_id": 4242}, format="json"
    )
    assert unlink_response.status_code == 200

    status_after_unlink = gateway_client.get("/api/v1/employees/telegram/status/", {"telegram_user_id": 4242})
    assert status_after_unlink.data["data"]["is_linked"] is False

    profile_after_unlink = gateway_client.get(
        "/api/v1/employees/telegram/profile/", {"telegram_user_id": 4242}
    )
    assert profile_after_unlink.status_code == 404
    assert profile_after_unlink.data["error"]["code"] == "employee_not_linked_to_telegram"


def test_request_link_sends_otp_to_both_work_and_personal_email(
    gateway_client, department, recording_email_client
) -> None:
    employee_with_personal_email = EmployeeRecord.objects.create(
        employee_code="E000003",
        first_name="Ada",
        last_name="Lovelace",
        work_email="ada.lovelace@example.com",
        personal_email="ada.personal@example.com",
        department=department,
        job_title="Software Engineer",
        employment_type="full_time",
        date_of_joining="2024-01-15",
    )

    response = gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee_with_personal_email.employee_code, "telegram_user_id": 88, "chat_id": 88},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert len(recording_email_client.sent) == 2
    sent_to = {message.to_email for message in recording_email_client.sent}
    assert sent_to == {"ada.lovelace@example.com", "ada.personal@example.com"}
    # Both emails carry the identical OTP — verifying with either should work.
    assert _extract_otp(recording_email_client.sent[0]) == _extract_otp(recording_email_client.sent[1])


def test_request_link_rejects_unknown_employee_code(gateway_client, recording_email_client) -> None:
    response = gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": "E999999", "telegram_user_id": 1, "chat_id": 1},
        format="json",
    )

    assert response.status_code == 404
    assert response.data["error"]["code"] == "employee_not_found"


def test_verify_link_rejects_wrong_otp(gateway_client, employee, recording_email_client) -> None:
    gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 55, "chat_id": 55},
        format="json",
    )

    response = gateway_client.post(
        "/api/v1/employees/telegram/link/verify/",
        {"telegram_user_id": 55, "chat_id": 55, "otp": "000000"},
        format="json",
    )

    assert response.status_code == 422
    assert response.data["error"]["code"] == "invalid_employee_link_otp"


def test_request_link_rejects_telegram_id_already_linked_to_another_employee(
    gateway_client, employee, department, recording_email_client
) -> None:
    other_employee = EmployeeRecord.objects.create(
        employee_code="E000002",
        first_name="Ada",
        last_name="Lovelace",
        work_email="ada.lovelace@example.com",
        department=department,
        job_title="Software Engineer",
        employment_type="full_time",
        date_of_joining="2024-01-15",
    )
    gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": other_employee.employee_code, "telegram_user_id": 77, "chat_id": 77},
        format="json",
    )
    otp = _extract_otp(recording_email_client.sent[-1])
    gateway_client.post(
        "/api/v1/employees/telegram/link/verify/",
        {"telegram_user_id": 77, "chat_id": 77, "otp": otp},
        format="json",
    )

    response = gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 77, "chat_id": 77},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "duplicate_telegram_link"


def test_request_link_rejects_employee_already_linked_to_a_different_telegram_account(
    gateway_client, employee, recording_email_client
) -> None:
    gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 111, "chat_id": 111},
        format="json",
    )
    otp = _extract_otp(recording_email_client.sent[-1])
    gateway_client.post(
        "/api/v1/employees/telegram/link/verify/",
        {"telegram_user_id": 111, "chat_id": 111, "otp": otp},
        format="json",
    )

    # A *different* Telegram account now tries to claim the same employee.
    response = gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 222, "chat_id": 222},
        format="json",
    )

    assert response.status_code == 409
    assert response.data["error"]["code"] == "employee_already_linked_to_telegram"
    # No OTP should have gone out for the rejected attempt — still just the
    # one email from the original, successful link.
    assert len(recording_email_client.sent) == 1


def test_request_link_allows_re_requesting_otp_for_the_same_linked_telegram_account(
    gateway_client, employee, recording_email_client
) -> None:
    gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 111, "chat_id": 111},
        format="json",
    )
    otp = _extract_otp(recording_email_client.sent[-1])
    gateway_client.post(
        "/api/v1/employees/telegram/link/verify/",
        {"telegram_user_id": 111, "chat_id": 111, "otp": otp},
        format="json",
    )

    # The same already-linked account asks for another code — allowed.
    response = gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 111, "chat_id": 111},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert len(recording_email_client.sent) == 2


def test_verify_link_locks_out_after_too_many_wrong_attempts(
    gateway_client, employee, recording_email_client
) -> None:
    gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 66, "chat_id": 66},
        format="json",
    )
    real_otp = _extract_otp(recording_email_client.sent[-1])
    wrong_otp = "000000" if real_otp != "000000" else "111111"

    for _ in range(5):  # MAX_OTP_ATTEMPTS
        response = gateway_client.post(
            "/api/v1/employees/telegram/link/verify/",
            {"telegram_user_id": 66, "chat_id": 66, "otp": wrong_otp},
            format="json",
        )
        assert response.status_code == 422
        assert response.data["error"]["code"] == "invalid_employee_link_otp"

    # Even the *correct* code is now rejected — the token is locked, not
    # just "still wrong."
    locked_response = gateway_client.post(
        "/api/v1/employees/telegram/link/verify/",
        {"telegram_user_id": 66, "chat_id": 66, "otp": real_otp},
        format="json",
    )
    assert locked_response.status_code == 422
    assert locked_response.data["error"]["code"] == "too_many_otp_attempts"


def test_verify_link_succeeds_within_the_attempt_budget(gateway_client, employee, recording_email_client) -> None:
    gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 67, "chat_id": 67},
        format="json",
    )
    real_otp = _extract_otp(recording_email_client.sent[-1])
    wrong_otp = "000000" if real_otp != "000000" else "111111"

    for _ in range(4):  # one below MAX_OTP_ATTEMPTS
        gateway_client.post(
            "/api/v1/employees/telegram/link/verify/",
            {"telegram_user_id": 67, "chat_id": 67, "otp": wrong_otp},
            format="json",
        )

    response = gateway_client.post(
        "/api/v1/employees/telegram/link/verify/",
        {"telegram_user_id": 67, "chat_id": 67, "otp": real_otp},
        format="json",
    )

    assert response.status_code == 200, response.data
    assert response.data["data"]["is_linked_to_telegram"] is True


def test_request_link_reports_email_delivery_failure(monkeypatch, gateway_client, employee) -> None:
    class _AlwaysFailingEmailClient:
        def send(self, message):
            from shared_kernel.infrastructure.email_client import EmailDeliveryError

            raise EmailDeliveryError("Simulated SMTP outage")

    monkeypatch.setattr(dependencies, "_build_email_client", lambda: _AlwaysFailingEmailClient())

    response = gateway_client.post(
        "/api/v1/employees/telegram/link/request/",
        {"employee_code": employee.employee_code, "telegram_user_id": 1, "chat_id": 1},
        format="json",
    )

    assert response.status_code == 502
    assert response.data["error"]["code"] == "email_delivery_failed"
