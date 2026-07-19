"""OTP delivery for Telegram linking, over real email.

Composes the business-specific message (subject/body wording) and hands it
to shared_kernel.infrastructure.email_client.EmailClientPort for actual
transport — this class owns *what the email says*, not *how it's sent*,
matching the split shared_kernel's email_client module documents.

send_link_otp fans out to every address in `to_emails` as separate
EmailClientPort.send() calls (one EmailMessage per recipient), rather than
listing every address on a single message's "To" line — each employee
should see their own address only, and EmailClientPort.send()/EmailMessage
were already a single-recipient primitive (see shared_kernel's
email_client module), so this keeps that contract unchanged instead of
teaching the generic transport layer about multi-recipient delivery for
what is, so far, a single business caller's need.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence

from apps.employees.application.ports import EmployeeOTPEmailPort
from shared_kernel.infrastructure.email_client import EmailClientPort, EmailDeliveryError, EmailMessage

logger = logging.getLogger(__name__)

_SUBJECT = "Your United HRMS Telegram verification code"


def _body_text(*, employee_name: str, otp: str) -> str:
    return (
        f"Hi {employee_name},\n\n"
        f"Your one-time verification code to link your Telegram account is: {otp}\n\n"
        "This code expires in 10 minutes. If you did not request this, you can safely "
        "ignore this email — your account has not been linked.\n\n"
        "— United HRMS"
    )


def _body_html(*, employee_name: str, otp: str) -> str:
    return (
        f"<p>Hi {employee_name},</p>"
        f"<p>Your one-time verification code to link your Telegram account is: "
        f"<strong style=\"font-size:1.25em;letter-spacing:0.1em\">{otp}</strong></p>"
        "<p>This code expires in 10 minutes. If you did not request this, you can safely "
        "ignore this email — your account has not been linked.</p>"
        "<p>— United HRMS</p>"
    )


class EmployeeOTPEmailSender(EmployeeOTPEmailPort):
    def __init__(self, email_client: EmailClientPort) -> None:
        self._email_client = email_client

    def send_link_otp(self, *, to_emails: Sequence[str], employee_name: str, otp: str) -> None:
        to_emails = list(to_emails)
        failures: list[tuple[str, EmailDeliveryError]] = []
        for to_email in to_emails:
            try:
                self._email_client.send(
                    EmailMessage(
                        to_email=to_email,
                        subject=_SUBJECT,
                        body_text=_body_text(employee_name=employee_name, otp=otp),
                        body_html=_body_html(employee_name=employee_name, otp=otp),
                    )
                )
            except EmailDeliveryError as exc:
                failures.append((to_email, exc))

        if not failures:
            return
        if len(failures) < len(to_emails):
            # At least one recipient got the code — that's still a usable
            # delivery for the employee, so this is worth knowing about
            # (ops/monitoring) but not worth failing the whole request_link
            # call over. See this port's docstring for why only a *total*
            # failure propagates.
            for to_email, exc in failures:
                logger.warning(
                    "OTP email failed for %s, but at least one other recipient succeeded: %s", to_email, exc
                )
            return

        raise EmailDeliveryError(
            f"Failed to deliver the OTP email to all {len(to_emails)} recipient(s): "
            + "; ".join(f"{to_email} ({exc})" for to_email, exc in failures)
        )
