"""Password reset email delivery.

This is the "implementation optional" part of the password reset
architecture: LoggingEmailSender logs the reset link instead of sending a
real email, since no SMTP/SES/SendGrid provider is configured yet. Every use
case that needs to send a reset email depends only on EmailSenderPort
(application/ports.py) — swapping this for a real provider later is a
one-file change, no use case is touched.
"""
from __future__ import annotations

import logging

from apps.identity.application.ports import EmailSenderPort

logger = logging.getLogger(__name__)


class LoggingEmailSender(EmailSenderPort):
    def send_password_reset_email(self, *, to_email: str, raw_token: str) -> None:
        logger.info(
            "Password reset requested for %s — token (would be emailed, not logged in production): %s",
            to_email,
            raw_token,
        )
