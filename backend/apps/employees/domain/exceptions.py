"""Domain/application exceptions for Employees.

All subclass shared_kernel's DomainError (or one of its subclasses), so the
API layer never needs Employee-specific exception handling — matching
Identity's precedent exactly (apps/identity/domain/exceptions.py).
"""
from __future__ import annotations

from shared_kernel.api.exceptions import (
    ConflictError,
    DomainError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)


class EmployeeNotFoundError(NotFoundError):
    """No employee was found matching the given identifier."""

    code = "employee_not_found"


class DepartmentNotFoundError(NotFoundError):
    """No department was found matching the given identifier."""

    code = "department_not_found"


class DuplicateEmployeeCodeError(ConflictError):
    """An employee with this employee code already exists."""

    code = "duplicate_employee_code"


class DuplicateWorkEmailError(ConflictError):
    """An employee with this work email already exists."""

    code = "duplicate_work_email"


class DuplicateDepartmentCodeError(ConflictError):
    """Phase 12 (Department CRUD): a department with this code already exists."""

    code = "duplicate_department_code"


class InvalidDepartmentParentError(ValidationError):
    """Phase 12 (Department CRUD): a department cannot be its own parent."""

    code = "invalid_department_parent"


class UserAlreadyLinkedError(ConflictError):
    """This user account is already linked to a different employee."""

    code = "user_already_linked"


class UserNotFoundError(NotFoundError):
    """Phase 12 (link an existing employee to an existing user): the given
    user_id doesn't exist in Identity. Deliberately the same `code` as
    `apps.identity.domain.exceptions.UserNotFoundError` — both mean "no
    User with this id," just raised from a different module's validation;
    keeping the wire-level code identical is more useful to a frontend
    than differentiating them would be."""

    code = "user_not_found"


class InvalidEmployeeStatusTransitionError(InvalidStateTransitionError):
    """This status change is not valid from the employee's current status."""

    code = "invalid_employee_status_transition"


class InvalidCurrentStatusTransitionError(InvalidStateTransitionError):
    """Round 14 item 8 — this Current Status change is not valid: either the
    employee's current_status is terminal (Terminated/Resigned), or the
    target is a system-managed leave status a manual update may never set,
    or the employee is on an auto-managed leave status and this change
    isn't the one manual exception (Terminated/Resigned)."""

    code = "invalid_current_status_transition"


# --- Telegram linking (Employee & Telegram Authentication refactor) ------
# Moved from apps/identity/domain/exceptions.py — the analogous concept for
# password-reset tokens (InvalidResetTokenError/ExpiredResetTokenError)
# lives in Identity because passwords are an Identity concern; Telegram
# linking is now an Employee concern in exactly the same way.


class DuplicateTelegramLinkError(ConflictError):
    """This Telegram account is already linked to a different employee."""

    code = "duplicate_telegram_link"


class EmployeeNotLinkedToTelegramError(NotFoundError):
    """No employee is linked to this Telegram account."""

    code = "employee_not_linked_to_telegram"


class EmployeeNotActiveError(ValidationError):
    """This action is not permitted for a terminated employee."""

    code = "employee_not_active"


class InvalidEmployeeLinkOTPError(ValidationError):
    """This Telegram-linking OTP is invalid or has already been used."""

    code = "invalid_employee_link_otp"


class ExpiredEmployeeLinkOTPError(ValidationError):
    """This Telegram-linking OTP has expired."""

    code = "expired_employee_link_otp"


class EmployeeAlreadyLinkedToTelegramError(ConflictError):
    """This employee is already linked to a different Telegram account.

    Distinct from DuplicateTelegramLinkError, which is the mirror-image
    check ("this Telegram account already belongs to a different
    employee"). Raised by request_link, before any OTP is generated or
    sent — re-linking is not silently allowed (Employee.link_telegram()
    itself has no opinion on this; enforcing it is this service's job, not
    the entity's — see that method's docstring). The employee must
    explicitly /unlink from their current Telegram account first, or
    contact HR — this is a deliberate choice, not an oversight: silently
    overwriting an existing link on request would let anyone who knows (or
    guesses) an employee_code start a re-link attempt against them with no
    notice to the original linked account.
    """

    code = "employee_already_linked_to_telegram"


class TooManyOTPAttemptsError(ValidationError):
    """This OTP has been guessed wrong too many times and is now locked;
    request a new one."""

    code = "too_many_otp_attempts"


class OTPEmailDeliveryFailedError(DomainError):
    """The OTP was generated and stored, but could not be emailed to any of
    the employee's registered addresses.

    Deliberately not a ValidationError/ConflictError/NotFoundError: this
    isn't a business-rule violation, it's an upstream dependency (the mail
    transport) failing — a 502 more accurately describes "we depend on
    something that just failed" than a 4xx describes "you did something
    wrong." See EmployeeTelegramLinkingService.request_link, which catches
    shared_kernel.infrastructure.email_client.EmailDeliveryError and
    re-raises this in its place — the application layer is allowed to know
    about EmailDeliveryError because EmployeeOTPEmailPort.send_link_otp's
    own contract documents that it can raise it (see application/ports.py);
    it does not mean the application layer depends on any concrete email
    transport.
    """

    code = "email_delivery_failed"
    status_code = 502
