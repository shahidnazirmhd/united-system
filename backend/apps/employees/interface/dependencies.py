"""Composition root for the Employee module's services.

Matches Identity's interface/dependencies.py pattern exactly: the ViewSet
never constructs infrastructure classes directly, it calls one of these
factory functions — the one file in this module allowed to import both
application-layer services and infrastructure-layer implementations
together.
"""
from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

from apps.employees.application.ports import EmployeeOTPEmailPort
from apps.employees.application.services.department_command_service import DepartmentCommandService
from apps.employees.application.services.department_query_service import DepartmentQueryService
from apps.employees.application.services.department_service import DepartmentService
from apps.employees.application.services.employee_command_service import EmployeeCommandService
from apps.employees.application.services.employee_query_service import EmployeeQueryService
from apps.employees.application.services.employee_service import EmployeeService
from apps.employees.application.services.employee_telegram_linking_service import (
    EmployeeTelegramLinkingService,
)
from apps.employees.infrastructure.otp_email_sender import EmployeeOTPEmailSender
from apps.employees.infrastructure.repositories import (
    DjangoDepartmentRepository,
    DjangoEmployeeLinkTokenRepository,
    DjangoEmployeeRepository,
)
from apps.employees.infrastructure.leave_reference_check_adapter import LeaveServiceReferenceCheckAdapter
from apps.employees.infrastructure.user_lookup_adapter import UserServiceLookupAdapter
from shared_kernel.infrastructure.django_unit_of_work import DjangoUnitOfWork
from shared_kernel.infrastructure.event_bus_impl import event_bus
from shared_kernel.infrastructure.email_client import EmailClientPort, LoggingEmailClient, SmtpEmailClient


def build_employee_command_service() -> EmployeeCommandService:
    return EmployeeCommandService(
        employee_repository=DjangoEmployeeRepository(),
        department_repository=DjangoDepartmentRepository(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
        user_lookup=UserServiceLookupAdapter(),
        # HR Leave Workflow round, item 2 — see LeaveReferenceCheckPort's
        # docstring (application/ports.py) for the reverse-dependency
        # reasoning (Employees depends on Leave, never the other way).
        leave_reference_check=LeaveServiceReferenceCheckAdapter(),
    )


def build_employee_query_service() -> EmployeeQueryService:
    return EmployeeQueryService(
        employee_repository=DjangoEmployeeRepository(),
        department_repository=DjangoDepartmentRepository(),
        user_lookup=UserServiceLookupAdapter(),
    )


def build_employee_service() -> EmployeeService:
    return EmployeeService(
        command_service=build_employee_command_service(),
        query_service=build_employee_query_service(),
    )


def build_department_command_service() -> DepartmentCommandService:
    return DepartmentCommandService(
        department_repository=DjangoDepartmentRepository(),
        employee_repository=DjangoEmployeeRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_department_query_service() -> DepartmentQueryService:
    return DepartmentQueryService(
        department_repository=DjangoDepartmentRepository(),
        employee_repository=DjangoEmployeeRepository(),
    )


def build_department_service() -> DepartmentService:
    return DepartmentService(
        command_service=build_department_command_service(),
        query_service=build_department_query_service(),
    )


def _build_email_client() -> EmailClientPort:
    # SMTP_HOST unset (local dev with no mail provider configured) ->
    # LoggingEmailClient, matching every other "implementation optional"
    # port in this codebase (LoggingEmailSender, the old LoggingOTPSender).
    # Set SMTP_HOST (see .env.example) to send real email.
    if not settings.SMTP_HOST:
        return LoggingEmailClient()

    _warn_if_gmail_from_mismatch()
    return SmtpEmailClient(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME or None,
        password=settings.SMTP_PASSWORD or None,
        use_tls=settings.SMTP_USE_TLS,
        from_email=settings.SMTP_FROM_EMAIL,
        from_name=settings.SMTP_FROM_NAME,
        timeout_seconds=settings.SMTP_TIMEOUT_SECONDS,
    )


def _warn_if_gmail_from_mismatch() -> None:
    """The single most common cause of Gmail-relayed OTP mail landing in
    Spam isn't content, it's identity mismatch: authenticating as
    your-temp-account@gmail.com (SMTP_USERNAME) but claiming to be From
    no-reply@united-hrms.local (a domain with no MX/SPF/DKIM/DMARC records
    at all, since it doesn't really exist) looks exactly like the header
    spoofing spam filters are built to catch — Gmail's own outbound
    filtering can downgrade it before it even reaches the recipient. There
    is no code fix for this beyond making SMTP_FROM_EMAIL match
    SMTP_USERNAME (or a verified Gmail "Send As" alias of it) — see
    .env.example's Gmail setup steps, which already say this; this is a
    loud, one-time-per-process log line for anyone who skipped straight to
    filling in placeholders without reading them.
    """
    if "gmail.com" not in settings.SMTP_HOST.lower():
        return
    from_domain = settings.SMTP_FROM_EMAIL.rsplit("@", 1)[-1].lower()
    username_domain = settings.SMTP_USERNAME.rsplit("@", 1)[-1].lower() if settings.SMTP_USERNAME else ""
    if from_domain != username_domain:
        logger.warning(
            "SMTP_FROM_EMAIL (%s) doesn't match the domain of the Gmail account "
            "SMTP_USERNAME authenticates as (%s). Gmail will very likely deliver "
            "this to the recipient's Spam folder, or reject it outright, because "
            "the From address can't be verified against the account that's actually "
            "sending it. Set SMTP_FROM_EMAIL to the same address as SMTP_USERNAME "
            "(or a verified 'Send As' alias of it) — see .env.example.",
            settings.SMTP_FROM_EMAIL,
            settings.SMTP_USERNAME,
        )


def _build_otp_email_sender() -> EmployeeOTPEmailPort:
    return EmployeeOTPEmailSender(email_client=_build_email_client())


def build_employee_telegram_linking_service() -> EmployeeTelegramLinkingService:
    return EmployeeTelegramLinkingService(
        employee_repository=DjangoEmployeeRepository(),
        link_token_repository=DjangoEmployeeLinkTokenRepository(),
        otp_email_sender=_build_otp_email_sender(),
        unit_of_work=DjangoUnitOfWork(),
        event_bus=event_bus,
    )
