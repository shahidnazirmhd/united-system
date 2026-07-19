"""Employee <-> Telegram linking: request an OTP, verify it, check status,
unlink. The Employee-module equivalent of Identity's (removed) Telegram
use cases, redesigned around the refactored flow —
TELEGRAM_GATEWAY.md's Authentication Flow section:

    Employee starts the bot -> enters Employee ID -> Gateway calls the
    HR API -> Employee is validated -> OTP generated -> OTP sent to the
    employee's registered email(s) -> Employee enters OTP -> OTP verified ->
    Telegram ID stored on the Employee record -> registration complete.

    "Registered email(s)" is deliberately plural: the OTP always goes to
    work_email (mandatory on every Employee), and additionally to
    personal_email when the employee has one on file (optional field on
    ContactInformation) — see request_link's _otp_recipient_emails call.
    Sending to both gives the employee a second, non-work channel to
    receive the code on if they don't have easy access to their work inbox
    at the moment they're standing in front of the bot.

No identity.User is ever created or looked up here — every method takes
and returns only Employee-shaped data. One class with several methods
(not one-class-per-use-case) because every method shares the exact same
four dependencies and there is no meaningful independent-testability
argument for splitting them, matching EmployeeCommandService/
EmployeeQueryService's precedent of "a service is the right shape when a
whole related family of operations shares one dependency set."
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from apps.employees.application.dtos import (
    EmployeeResponse,
    EmployeeTelegramLinkStatusResponse,
    RequestEmployeeTelegramLinkRequest,
    VerifyEmployeeTelegramLinkRequest,
)
from apps.employees.application.mappers import employee_to_response
from apps.employees.application.ports import EmployeeOTPEmailPort
from apps.employees.domain.entities import Employee, EmployeeLinkToken
from apps.employees.domain.enums import EmployeeStatus
from apps.employees.domain.events import (
    EmployeeTelegramLinked,
    EmployeeTelegramLinkRequested,
    EmployeeTelegramUnlinked,
)
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
from apps.employees.domain.repositories import EmployeeLinkTokenRepository, EmployeeRepository
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.email_client import EmailDeliveryError
from shared_kernel.infrastructure.uuid7 import generate_uuid7

LINK_OTP_LIFETIME = timedelta(minutes=10)
OTP_LENGTH = 6
# See TooManyOTPAttemptsError's docstring and EmployeeLinkToken.attempt_count
# for the reasoning: 5 wrong guesses out of 1,000,000 possible 6-digit codes
# is a negligible brute-force success rate, while still generous enough that
# a couple of fat-fingered typos don't cost the employee their pending link.
MAX_OTP_ATTEMPTS = 5


def _generate_otp() -> str:
    # secrets.choice, not `random` — this is a security credential (see
    # EmployeeLinkToken's docstring), same discipline as
    # apps.identity.application.use_cases.request_password_reset's
    # secrets.token_urlsafe for password reset tokens.
    return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _otp_recipient_emails(employee: Employee) -> list[str]:
    """work_email is mandatory on every Employee, so it's always first.
    personal_email is optional (ContactInformation.personal_email) and only
    appended when set. Deduplicated (order-preserving) purely as cheap
    insurance against sending the identical OTP email twice in the rare
    case the two fields happen to hold the same address — not a real-world
    expectation, just avoids a redundant send if it ever happens.
    """
    emails = [str(employee.contact_info.work_email)]
    if employee.contact_info.personal_email is not None:
        personal_email = str(employee.contact_info.personal_email)
        if personal_email not in emails:
            emails.append(personal_email)
    return emails


class EmployeeTelegramLinkingService:
    def __init__(
        self,
        employee_repository: EmployeeRepository,
        link_token_repository: EmployeeLinkTokenRepository,
        otp_email_sender: EmployeeOTPEmailPort,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        self._employees = employee_repository
        self._link_tokens = link_token_repository
        self._otp_email_sender = otp_email_sender
        self._uow = unit_of_work
        self._event_bus = event_bus

    def request_link(self, request: RequestEmployeeTelegramLinkRequest) -> None:
        """Always raises EmployeeNotFoundError for an unknown employee_code
        rather than silently no-op'ing (unlike password reset's deliberate
        email-enumeration protection) — the employee_code is typed in
        directly by the person using the bot as the very first step of the
        flow, so telling them it's wrong is the whole point of this step,
        not an information leak. There is no "does this email exist"
        question being protected against here.
        """
        employee = self._employees.get_by_employee_code(request.employee_code)
        if employee is None:
            raise EmployeeNotFoundError()

        if employee.status == EmployeeStatus.TERMINATED:
            raise EmployeeNotActiveError(
                f"Cannot link Telegram for a terminated employee ({employee.employee_code})."
            )

        # This employee already has a *different* Telegram account linked —
        # reject before generating/sending any OTP, rather than silently
        # letting a fresh /link overwrite it (Employee.link_telegram() itself
        # has no opinion on this by design — see its docstring; enforcing it
        # is this service's job). Re-linking is still possible, just not
        # silent: the employee must /unlink from the current account first.
        # A retry with the *same* telegram_user_id (re-requesting a code for
        # an already-linked chat) is deliberately allowed through unchanged —
        # that's just "I lost the first code, send another," not a re-link.
        if employee.is_linked_to_telegram and employee.telegram_user_id != request.telegram_user_id:
            raise EmployeeAlreadyLinkedToTelegramError()

        existing_link_holder = self._employees.get_by_telegram_user_id(request.telegram_user_id)
        if existing_link_holder is not None and existing_link_holder.id != employee.id:
            raise DuplicateTelegramLinkError()

        otp = _generate_otp()
        token = EmployeeLinkToken(
            id=generate_uuid7(),
            employee_id=employee.id,
            token=_hash_otp(otp),
            telegram_user_id=request.telegram_user_id,
            chat_id=request.chat_id,
            telegram_username=request.telegram_username,
            expires_at=datetime.now(timezone.utc) + LINK_OTP_LIFETIME,
        )
        with self._uow:
            self._link_tokens.create(token)

        try:
            self._otp_email_sender.send_link_otp(
                to_emails=_otp_recipient_emails(employee),
                employee_name=employee.profile.full_name,
                otp=otp,
            )
        except EmailDeliveryError as exc:
            # The token is already committed — a subsequent /link retry
            # creates a fresh one; this one simply expires unused in 10
            # minutes. Re-raised as a DomainError (502) rather than left to
            # propagate as a raw infrastructure exception, so the API
            # boundary and the Gateway's friendly-message mapping both see
            # a well-defined error instead of an opaque 500 — see
            # OTPEmailDeliveryFailedError's docstring.
            raise OTPEmailDeliveryFailedError() from exc

        self._event_bus.publish(
            EmployeeTelegramLinkRequested(employee_id=employee.id, telegram_user_id=request.telegram_user_id)
        )

    def verify_link(self, request: VerifyEmployeeTelegramLinkRequest) -> EmployeeResponse:
        # Looked up by (telegram_user_id, chat_id) — "the pending link
        # attempt for this chat" — not by the OTP's own hash. A hash lookup
        # can never distinguish "wrong code" from "no such request in
        # progress," which is exactly what makes attempt-counting
        # impossible with that approach: a wrong guess's hash matches no
        # row at all, so there is nothing to increment. See
        # EmployeeLinkTokenRepository.get_pending_by_chat's docstring.
        token = self._link_tokens.get_pending_by_chat(
            telegram_user_id=request.telegram_user_id, chat_id=request.chat_id
        )
        if token is None:
            raise InvalidEmployeeLinkOTPError()

        now = datetime.now(timezone.utc)
        if now >= token.expires_at:
            raise ExpiredEmployeeLinkOTPError()

        if token.attempt_count >= MAX_OTP_ATTEMPTS:
            raise TooManyOTPAttemptsError()

        if _hash_otp(request.otp) != token.token:
            self._link_tokens.increment_attempt_count(token.token)
            raise InvalidEmployeeLinkOTPError()

        employee = self._employees.get_by_id(token.employee_id)
        if employee is None:
            raise EmployeeNotFoundError()

        existing_link_holder = self._employees.get_by_telegram_user_id(request.telegram_user_id)
        if existing_link_holder is not None and existing_link_holder.id != employee.id:
            raise DuplicateTelegramLinkError()

        linked_employee = employee.link_telegram(
            telegram_user_id=request.telegram_user_id,
            chat_id=request.chat_id,
            telegram_username=request.telegram_username or token.telegram_username,
            linked_at=now,
        )
        with self._uow:
            saved = self._employees.update(linked_employee)
            self._link_tokens.mark_used(token.token, used_at=now)

        self._event_bus.publish(
            EmployeeTelegramLinked(employee_id=saved.id, telegram_user_id=request.telegram_user_id)
        )
        return employee_to_response(saved)

    def get_link_status(self, telegram_user_id: int) -> EmployeeTelegramLinkStatusResponse:
        employee = self._employees.get_by_telegram_user_id(telegram_user_id)
        if employee is None:
            return EmployeeTelegramLinkStatusResponse(is_linked=False, telegram_username=None, linked_at=None)
        return EmployeeTelegramLinkStatusResponse(
            is_linked=True,
            telegram_username=employee.telegram_username,
            linked_at=employee.telegram_linked_at,
        )

    def unlink(self, telegram_user_id: int) -> None:
        employee = self._employees.get_by_telegram_user_id(telegram_user_id)
        if employee is None:
            raise EmployeeNotLinkedToTelegramError()

        unlinked_employee = employee.unlink_telegram()
        with self._uow:
            self._employees.update(unlinked_employee)
        self._event_bus.publish(EmployeeTelegramUnlinked(employee_id=employee.id))
