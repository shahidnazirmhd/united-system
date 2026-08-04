"""Unit tests for EmployeeTelegramLinkingService — every dependency is a
hand-rolled fake, no Django, no database, no real SMTP. Same discipline as
test_employee_command_service.py and (the now-removed)
apps/identity/tests/unit/test_telegram_linking_use_cases.py, redesigned
around the Employee-owned flow (no identity.User is ever created).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from apps.employees.application.dtos import (
    RequestEmployeeTelegramLinkRequest,
    VerifyEmployeeTelegramLinkRequest,
)
from apps.employees.application.services.employee_telegram_linking_service import (
    EmployeeTelegramLinkingService,
)
from apps.employees.domain.entities import Employee, EmployeeLinkToken
from apps.employees.domain.enums import EmployeeStatus, EmploymentType
from apps.employees.domain.exceptions import (
    DuplicateTelegramLinkError,
    EmployeeAlreadyLinkedToTelegramError,
    EmployeeNotActiveError,
    EmployeeNotFoundError,
    EmployeeNotLinkedToTelegramError,
    ExpiredEmployeeLinkOTPError,
    InvalidEmployeeLinkOTPError,
    OTPEmailDeliveryFailedError,
    TooManyOTPAttemptsError,
)
from apps.employees.domain.value_objects import ContactInformation, EmployeeProfile, EmploymentInformation
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.value_objects import Email
from shared_kernel.infrastructure.email_client import EmailDeliveryError


class FakeUnitOfWork(UnitOfWork):
    def commit(self):
        pass

    def rollback(self):
        pass


class FakeEventBus(EventBus):
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)

    def subscribe(self, event_type, handler):
        pass


class FakeEmployeeRepository:
    def __init__(self, employees: list[Employee] | None = None):
        self._employees = {e.id: e for e in (employees or [])}

    def get_by_id(self, entity_id):
        return self._employees.get(entity_id)

    def get_by_employee_code(self, employee_code):
        return next((e for e in self._employees.values() if e.employee_code == employee_code), None)

    def get_by_work_email(self, work_email):
        return None

    def get_by_user_id(self, user_id):
        return None

    def get_by_telegram_user_id(self, telegram_user_id):
        return next((e for e in self._employees.values() if e.telegram_user_id == telegram_user_id), None)

    def exists_with_telegram_user_id(self, telegram_user_id):
        return self.get_by_telegram_user_id(telegram_user_id) is not None

    def exists_with_employee_code(self, employee_code):
        return self.get_by_employee_code(employee_code) is not None

    def exists_with_work_email(self, work_email):
        return False

    def next_employee_code(self):
        raise NotImplementedError("not exercised by these tests")

    def list(self, query):
        raise NotImplementedError("not exercised by these tests")

    def create(self, entity):
        self._employees[entity.id] = entity
        return entity

    def update(self, entity):
        self._employees[entity.id] = entity
        return entity

    def delete(self, entity_id):
        self._employees.pop(entity_id, None)

    def exists(self, entity_id):
        return entity_id in self._employees


class FakeEmployeeLinkTokenRepository:
    def __init__(self):
        self._by_hash: dict[str, EmployeeLinkToken] = {}
        self._insertion_order: list[str] = []  # oldest first

    def create(self, token):
        self._by_hash[token.token] = token
        self._insertion_order.append(token.token)
        return token

    def get_pending_by_chat(self, *, telegram_user_id, chat_id):
        # Most-recently-created match, mirroring
        # DjangoEmployeeLinkTokenRepository's `.order_by("-created_at")`.
        for token_hash in reversed(self._insertion_order):
            token = self._by_hash.get(token_hash)
            if (
                token is not None
                and token.used_at is None
                and token.telegram_user_id == telegram_user_id
                and token.chat_id == chat_id
            ):
                return token
        return None

    def increment_attempt_count(self, token):
        existing = self._by_hash.get(token)
        if existing is not None:
            self._by_hash[token] = self._replace(existing, attempt_count=existing.attempt_count + 1)

    def mark_used(self, token, *, used_at):
        existing = self._by_hash.get(token)
        if existing is not None:
            self._by_hash[token] = self._replace(existing, used_at=used_at)

    @staticmethod
    def _replace(existing: EmployeeLinkToken, **changes) -> EmployeeLinkToken:
        return EmployeeLinkToken(
            id=existing.id,
            employee_id=existing.employee_id,
            token=existing.token,
            telegram_user_id=existing.telegram_user_id,
            chat_id=existing.chat_id,
            telegram_username=existing.telegram_username,
            expires_at=existing.expires_at,
            used_at=changes.get("used_at", existing.used_at),
            attempt_count=changes.get("attempt_count", existing.attempt_count),
        )


class FakeOTPEmailSender:
    def __init__(self, fail_with: Exception | None = None):
        self.sent: list[dict] = []
        self._fail_with = fail_with

    def send_link_otp(self, *, to_emails, employee_name, otp):
        if self._fail_with is not None:
            raise self._fail_with
        self.sent.append({"to_emails": list(to_emails), "employee_name": employee_name, "otp": otp})


def _employee(**overrides) -> Employee:
    status = overrides.pop("status", EmployeeStatus.ACTIVE)
    personal_email = overrides.pop("personal_email", None)
    return Employee(
        id=overrides.pop("id", uuid.uuid4()),
        employee_code=overrides.pop("employee_code", "E000001"),
        user_id=None,
        profile=EmployeeProfile(first_name="Grace", last_name="Hopper"),
        contact_info=ContactInformation(
            work_email=Email(overrides.pop("work_email", "grace@example.com")),
            personal_email=Email(personal_email) if personal_email else None,
        ),
        employment_info=EmploymentInformation(
            department_id=uuid.uuid4(),
            job_title="Rear Admiral",
            employment_type=EmploymentType.FULL_TIME,
            date_of_joining=date(2000, 1, 1),
        ),
        status=status,
        telegram_user_id=overrides.pop("telegram_user_id", None),
        telegram_chat_id=overrides.pop("telegram_chat_id", None),
        telegram_username=overrides.pop("telegram_username", None),
        telegram_linked_at=overrides.pop("telegram_linked_at", None),
    )


def _service(employees=None, link_tokens=None, otp_sender=None):
    return EmployeeTelegramLinkingService(
        employee_repository=employees or FakeEmployeeRepository(),
        link_token_repository=link_tokens or FakeEmployeeLinkTokenRepository(),
        otp_email_sender=otp_sender or FakeOTPEmailSender(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
    )


# --- request_link ----------------------------------------------------


def test_request_link_dispatches_otp_to_work_email() -> None:
    employee = _employee(employee_code="E000001", work_email="grace@example.com")
    employees = FakeEmployeeRepository([employee])
    otp_sender = FakeOTPEmailSender()
    service = _service(employees=employees, otp_sender=otp_sender)

    service.request_link(
        RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=42, chat_id=42)
    )

    assert len(otp_sender.sent) == 1
    assert otp_sender.sent[0]["to_emails"] == ["grace@example.com"]
    assert len(otp_sender.sent[0]["otp"]) == 6


def test_request_link_dispatches_otp_to_both_work_and_personal_email() -> None:
    employee = _employee(
        employee_code="E000001", work_email="grace@example.com", personal_email="grace.h@personal.example.com"
    )
    employees = FakeEmployeeRepository([employee])
    otp_sender = FakeOTPEmailSender()
    service = _service(employees=employees, otp_sender=otp_sender)

    service.request_link(
        RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=42, chat_id=42)
    )

    assert len(otp_sender.sent) == 1
    assert otp_sender.sent[0]["to_emails"] == ["grace@example.com", "grace.h@personal.example.com"]


def test_request_link_dispatches_otp_once_when_personal_email_matches_work_email() -> None:
    employee = _employee(
        employee_code="E000001", work_email="grace@example.com", personal_email="grace@example.com"
    )
    employees = FakeEmployeeRepository([employee])
    otp_sender = FakeOTPEmailSender()
    service = _service(employees=employees, otp_sender=otp_sender)

    service.request_link(
        RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=42, chat_id=42)
    )

    assert otp_sender.sent[0]["to_emails"] == ["grace@example.com"]


def test_request_link_raises_for_unknown_employee_code() -> None:
    service = _service()

    with pytest.raises(EmployeeNotFoundError):
        service.request_link(
            RequestEmployeeTelegramLinkRequest(employee_code="E999999", telegram_user_id=1, chat_id=1)
        )


def test_request_link_raises_for_terminated_employee() -> None:
    employee = _employee(employee_code="E000001", status=EmployeeStatus.TERMINATED)
    service = _service(employees=FakeEmployeeRepository([employee]))

    with pytest.raises(EmployeeNotActiveError):
        service.request_link(
            RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=1, chat_id=1)
        )


def test_request_link_raises_when_telegram_id_linked_to_different_employee() -> None:
    other_employee_id = uuid.uuid4()
    already_linked = _employee(id=other_employee_id, employee_code="E000002", telegram_user_id=42)
    requester = _employee(employee_code="E000001")
    employees = FakeEmployeeRepository([already_linked, requester])
    service = _service(employees=employees)

    with pytest.raises(DuplicateTelegramLinkError):
        service.request_link(
            RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=42, chat_id=42)
        )


def test_request_link_raises_when_employee_already_linked_to_a_different_telegram_account() -> None:
    employee = _employee(employee_code="E000001", telegram_user_id=111)
    service = _service(employees=FakeEmployeeRepository([employee]))

    with pytest.raises(EmployeeAlreadyLinkedToTelegramError):
        service.request_link(
            RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=222, chat_id=222)
        )


def test_request_link_allows_re_requesting_otp_for_the_same_already_linked_telegram_account() -> None:
    """Re-requesting a code for the *same* chat that's already linked (e.g.
    the employee lost the confirmation and wants to double check, or is
    simply re-running /link out of habit) is not a re-link attempt and must
    not be blocked — only linking to a *different* Telegram account should
    require an explicit /unlink first."""
    employee = _employee(employee_code="E000001", telegram_user_id=111)
    otp_sender = FakeOTPEmailSender()
    service = _service(employees=FakeEmployeeRepository([employee]), otp_sender=otp_sender)

    service.request_link(
        RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=111, chat_id=111)
    )

    assert len(otp_sender.sent) == 1


def test_request_link_raises_otp_email_delivery_failed_when_every_recipient_fails() -> None:
    employee = _employee(employee_code="E000001")
    otp_sender = FakeOTPEmailSender(fail_with=EmailDeliveryError("SMTP server unavailable"))
    service = _service(employees=FakeEmployeeRepository([employee]), otp_sender=otp_sender)

    with pytest.raises(OTPEmailDeliveryFailedError):
        service.request_link(
            RequestEmployeeTelegramLinkRequest(employee_code="E000001", telegram_user_id=1, chat_id=1)
        )


# --- verify_link -------------------------------------------------------


def _requested_link(employees=None, link_tokens=None, otp_sender=None, employee_code="E000001"):
    """Runs request_link for real, then hands back the sent OTP string so
    a test can verify with it — avoids each verify_link test needing to
    reach into token internals to fabricate a valid hash by hand."""
    otp_sender = otp_sender or FakeOTPEmailSender()
    service = _service(employees=employees, link_tokens=link_tokens, otp_sender=otp_sender)
    service.request_link(
        RequestEmployeeTelegramLinkRequest(employee_code=employee_code, telegram_user_id=42, chat_id=99)
    )
    otp = otp_sender.sent[-1]["otp"]
    return service, otp


def test_verify_link_stores_telegram_id_on_employee() -> None:
    employee = _employee(employee_code="E000001")
    employees = FakeEmployeeRepository([employee])
    link_tokens = FakeEmployeeLinkTokenRepository()
    service, otp = _requested_link(employees=employees, link_tokens=link_tokens)

    result = service.verify_link(
        VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp=otp, telegram_username="ada")
    )

    assert result.is_linked_to_telegram is True
    assert result.telegram_username == "ada"
    stored = employees.get_by_id(employee.id)
    assert stored.telegram_user_id == 42
    assert stored.telegram_chat_id == 99


def test_verify_link_raises_for_wrong_otp() -> None:
    employee = _employee(employee_code="E000001")
    employees = FakeEmployeeRepository([employee])
    link_tokens = FakeEmployeeLinkTokenRepository()
    service, _otp = _requested_link(employees=employees, link_tokens=link_tokens)

    with pytest.raises(InvalidEmployeeLinkOTPError):
        service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp="000000"))


def test_verify_link_locks_out_after_max_attempts() -> None:
    employee = _employee(employee_code="E000001")
    employees = FakeEmployeeRepository([employee])
    link_tokens = FakeEmployeeLinkTokenRepository()
    service, otp = _requested_link(employees=employees, link_tokens=link_tokens)
    wrong_otp = "000000" if otp != "000000" else "111111"

    for _ in range(5):  # MAX_OTP_ATTEMPTS
        with pytest.raises(InvalidEmployeeLinkOTPError):
            service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp=wrong_otp))

    # The 6th attempt is locked out even though the *correct* OTP is used —
    # the token is spent, not just "still wrong."
    with pytest.raises(TooManyOTPAttemptsError):
        service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp=otp))


def test_verify_link_succeeds_within_the_attempt_budget() -> None:
    employee = _employee(employee_code="E000001")
    employees = FakeEmployeeRepository([employee])
    link_tokens = FakeEmployeeLinkTokenRepository()
    service, otp = _requested_link(employees=employees, link_tokens=link_tokens)
    wrong_otp = "000000" if otp != "000000" else "111111"

    for _ in range(4):  # one below MAX_OTP_ATTEMPTS
        with pytest.raises(InvalidEmployeeLinkOTPError):
            service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp=wrong_otp))

    result = service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp=otp))

    assert result.is_linked_to_telegram is True


def test_verify_link_raises_for_reused_otp() -> None:
    employee = _employee(employee_code="E000001")
    employees = FakeEmployeeRepository([employee])
    link_tokens = FakeEmployeeLinkTokenRepository()
    service, otp = _requested_link(employees=employees, link_tokens=link_tokens)

    service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp=otp))

    with pytest.raises(InvalidEmployeeLinkOTPError):
        service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp=otp))


def test_verify_link_raises_for_expired_otp() -> None:
    employee_id = uuid.uuid4()
    employee = _employee(id=employee_id, employee_code="E000001")
    employees = FakeEmployeeRepository([employee])
    link_tokens = FakeEmployeeLinkTokenRepository()
    expired_token = EmployeeLinkToken(
        id=uuid.uuid4(),
        employee_id=employee_id,
        token=hashlib.sha256(b"123456").hexdigest(),
        telegram_user_id=42,
        chat_id=99,
        telegram_username=None,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    link_tokens.create(expired_token)
    service = _service(employees=employees, link_tokens=link_tokens)

    with pytest.raises(ExpiredEmployeeLinkOTPError):
        service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=99, otp="123456"))


def test_verify_link_raises_when_chat_id_does_not_match_request() -> None:
    employee = _employee(employee_code="E000001")
    employees = FakeEmployeeRepository([employee])
    link_tokens = FakeEmployeeLinkTokenRepository()
    service, otp = _requested_link(employees=employees, link_tokens=link_tokens)

    with pytest.raises(InvalidEmployeeLinkOTPError):
        # chat_id=1 doesn't match the chat_id (99) request_link recorded.
        service.verify_link(VerifyEmployeeTelegramLinkRequest(telegram_user_id=42, chat_id=1, otp=otp))


# --- get_link_status / unlink -------------------------------------------


def test_get_link_status_reports_unlinked_for_unknown_telegram_id() -> None:
    service = _service()

    result = service.get_link_status(999)

    assert result.is_linked is False


def test_get_link_status_reports_linked() -> None:
    employee = _employee(
        telegram_user_id=42, telegram_username="ada", telegram_linked_at=datetime.now(timezone.utc)
    )
    service = _service(employees=FakeEmployeeRepository([employee]))

    result = service.get_link_status(42)

    assert result.is_linked is True
    assert result.telegram_username == "ada"


def test_unlink_clears_telegram_fields() -> None:
    employee = _employee(telegram_user_id=42, telegram_username="ada")
    employees = FakeEmployeeRepository([employee])
    service = _service(employees=employees)

    service.unlink(42)

    stored = employees.get_by_id(employee.id)
    assert stored.telegram_user_id is None
    assert stored.is_linked_to_telegram is False


def test_unlink_raises_when_not_linked() -> None:
    service = _service()

    with pytest.raises(EmployeeNotLinkedToTelegramError):
        service.unlink(999)
