"""Interfaces the Employee application layer depends on but does not
implement — Dependency Inversion, matching apps.identity's
application/ports.py precedent exactly.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence


class UserLookupPort(ABC):
    """Phase 12 (link an existing Employee to an existing Identity User) —
    the mirror image of `apps.leave.application.ports.EmployeeLookupPort`:
    that port is how Leave learns about Employees without importing that
    module's internals; this is how Employees learns whether a `user_id`
    it's about to link actually exists, without importing
    `apps.identity`'s domain/infrastructure. The concrete adapter
    (infrastructure/user_lookup_adapter.py) is the only file in this
    module allowed to import `apps.identity`, and even then only that
    module's already-composed public use cases (via its own
    `interface/dependencies.py`), never its ORM models directly.
    """

    @abstractmethod
    def user_exists(self, user_id: uuid.UUID) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_user_email(self, user_id: uuid.UUID) -> str | None:
        """Phase 12 bugfix: resolves the email of the User linked to an
        Employee, for the Employee Details page's "linked username/email"
        requirement. Returns None if user_id doesn't resolve to a real
        User (defensive — same reasoning as `user_exists`)."""
        raise NotImplementedError


class EmployeeOTPEmailPort(ABC):
    """Business-specific email port for Telegram-linking OTPs — composes
    the OTP into an actual email message and hands it to
    shared_kernel.infrastructure.email_client.EmailClientPort for
    transport-level delivery. See infrastructure/otp_email_sender.py for
    the concrete implementation and shared_kernel's email_client module
    docstring for why the split exists (generic transport vs. per-module
    business content).

    `to_emails` (plural): the OTP is sent to every address the employee has
    on file, not just one — see EmployeeTelegramLinkingService.request_link
    for how that list is built (always work_email, plus personal_email too
    when the employee has one). This port stays a plain "send to this set
    of addresses" primitive; it has no opinion on *which* addresses belong
    in the set — that's a business decision the service layer owns.

    Raises shared_kernel.infrastructure.email_client.EmailDeliveryError if
    *every* address in `to_emails` failed to send — see
    infrastructure/otp_email_sender.py's implementation for why a partial
    failure (e.g. work_email delivered, personal_email didn't) is logged
    but not raised: the employee still got a usable code. Callers that need
    to react to total delivery failure (see request_link's
    OTPEmailDeliveryFailedError) may catch EmailDeliveryError.
    """

    @abstractmethod
    def send_link_otp(self, *, to_emails: Sequence[str], employee_name: str, otp: str) -> None:
        raise NotImplementedError
