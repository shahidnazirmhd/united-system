"""Generic, transport-level email delivery — shared by every module that
needs to send an email, first consumer being
apps/employees/infrastructure (Telegram OTP delivery), alongside
apps/identity's own password-reset email.

Deliberately narrow: this port knows how to send *an* email (to, subject,
body). It knows nothing about passwords, OTPs, or any other business
concept — those belong to each module's own narrow port (e.g.
apps.identity.application.ports.EmailSenderPort,
apps.employees.application.ports.EmployeeOTPEmailPort), which composes a
business-specific message and hands it to this one for actual delivery.
This mirrors how PasswordHasherPort/TokenServicePort already sit in
apps/identity: shared_kernel owns generic infrastructure ports, modules own
the business-specific ports built on top of them.

apps.identity's existing `EmailSenderPort`/`LoggingEmailSender`
(apps/identity/application/ports.py, apps/identity/infrastructure/
email_sender.py) are deliberately left untouched by this refactor — they
already work, and rewiring them to delegate through this shared client is a
separate, non-urgent cleanup with no functional payoff today. Every *new*
email use in this codebase should depend on EmailClientPort, not
reintroduce another one-off logger-based sender.
"""
from __future__ import annotations

import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.headerregistry import Address
from email.message import EmailMessage as _MimeEmailMessage
from email.utils import formatdate, make_msgid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    body_text: str
    body_html: str | None = None


class EmailClientPort(ABC):
    @abstractmethod
    def send(self, message: EmailMessage) -> None:
        """Raises EmailDeliveryError if the message could not be handed off
        to the mail transport. Never raises for "unknown recipient" or
        similar — SMTP accepts-then-bounces asynchronously, so a successful
        `send()` only means "the mail server accepted it for delivery," not
        "the recipient received it." Callers that need delivery
        confirmation need a different mechanism (webhook/bounce handling),
        not this port.
        """
        raise NotImplementedError


class EmailDeliveryError(Exception):
    """Raised by EmailClientPort implementations when the underlying
    transport rejects or fails to send a message. Deliberately not a
    shared_kernel DomainError subclass: email delivery is an infrastructure
    concern, not a business rule violation, so a use case that catches this
    is choosing to (e.g. log and continue, per LoggingOTPSender's original
    "OTP still valid even if delivery fails" discipline), not required to.
    """


class SmtpEmailClient(EmailClientPort):
    """Production email delivery over SMTP, configured entirely from the
    SMTP_* environment variables (config/settings/base.py) — see
    .env.example for the full variable list and a step-by-step guide to
    configuring a temporary Gmail account for local development/testing.

    Uses Python's stdlib `smtplib` directly rather than Django's
    `django.core.mail` so this client's behavior is fully determined by its
    own constructor arguments (explicit Dependency Inversion — no hidden
    read of Django's global EMAIL_* settings), matching how every other
    infrastructure adapter in this codebase (PyJWTTokenService,
    DjangoPasswordHasher) takes its configuration explicitly rather than
    reaching into `django.conf.settings` itself. The composition root
    (each module's interface/dependencies.py) reads settings.SMTP_* once
    and passes the values in.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None,
        password: str | None,
        use_tls: bool,
        from_email: str,
        from_name: str = "United HRMS",
        timeout_seconds: int = 10,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._use_tls = use_tls
        self._from_email = from_email
        self._from_name = from_name
        self._timeout_seconds = timeout_seconds

    def send(self, message: EmailMessage) -> None:
        mime_message = _MimeEmailMessage()
        # A bare address in "From" (no display name) and a missing
        # Date/Message-ID are three of the more common, easily-fixed spam
        # signals — most real mail clients and every spam filter treat
        # their absence as evidence of an ad-hoc script rather than a real
        # mail system, regardless of content. None of this substitutes for
        # SPF/DKIM/DMARC (DNS-level, not fixable in code — see this class's
        # docstring and .env.example's Gmail setup notes for what those
        # require and why a personal Gmail account can only ever pass them
        # partially), but it removes the free, no-DNS-required part of the
        # problem.
        mime_message["From"] = Address(display_name=self._from_name, addr_spec=self._from_email)
        mime_message["To"] = message.to_email
        mime_message["Subject"] = message.subject
        mime_message["Date"] = formatdate(localtime=True)
        mime_message["Message-ID"] = make_msgid(domain=self._from_email.rsplit("@", 1)[-1])
        mime_message.set_content(message.body_text)
        if message.body_html:
            mime_message.add_alternative(message.body_html, subtype="html")

        try:
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds) as smtp:
                if self._use_tls:
                    smtp.starttls()
                if self._username and self._password:
                    smtp.login(self._username, self._password)
                smtp.send_message(mime_message)
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailDeliveryError(f"Failed to send email to {message.to_email}: {exc}") from exc


class LoggingEmailClient(EmailClientPort):
    """Dev-mode fallback: logs the message instead of sending it. Selected
    automatically when SMTP_HOST is not configured — see each module's
    interface/dependencies.py for the selection logic. Same
    "implementation optional" discipline as apps.identity's
    LoggingEmailSender.
    """

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "Email requested for %s — subject=%r (would be sent via SMTP, not logged in production): %s",
            message.to_email,
            message.subject,
            message.body_text,
        )
