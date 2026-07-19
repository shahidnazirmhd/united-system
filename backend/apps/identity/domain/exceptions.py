"""Domain/application exceptions for Identity.

All subclass shared_kernel's DomainError, so the API layer never needs
Identity-specific exception handling — shared_kernel/api/exception_handler.py
already knows how to turn any DomainError into the standard error envelope
(see CODING_STANDARD.md: "no business logic in views" extends to "no
exception-to-HTTP-status translation in views" either).
"""
from __future__ import annotations

from shared_kernel.api.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


class InvalidCredentialsError(DomainError):
    """The provided email or password is incorrect."""

    code = "invalid_credentials"
    status_code = 401


class InactiveUserError(DomainError):
    """This account has been deactivated."""

    code = "inactive_user"
    status_code = 401


class InvalidTokenError(DomainError):
    """The provided token is malformed, expired, or has an unexpected type."""

    code = "invalid_token"
    status_code = 401


class TokenRevokedError(DomainError):
    """This token has already been used or revoked."""

    code = "token_revoked"
    status_code = 401


class UserNotFoundError(NotFoundError):
    """No user was found matching the given identifier."""

    code = "user_not_found"


class RoleNotFoundError(NotFoundError):
    """No role was found matching the given identifier."""

    code = "role_not_found"


class PermissionNotFoundError(NotFoundError):
    """No permission was found matching the given code."""

    code = "permission_not_found"


class DuplicateEmailError(ConflictError):
    """A user with this email address already exists."""

    code = "duplicate_email"


class DuplicateRoleNameError(ConflictError):
    """A role with this name already exists."""

    code = "duplicate_role_name"


class RoleAlreadyAssignedError(ConflictError):
    """This user already holds this role."""

    code = "role_already_assigned"


class InvalidResetTokenError(ValidationError):
    """This password reset token is invalid or has already been used."""

    code = "invalid_reset_token"


class ExpiredResetTokenError(ValidationError):
    """This password reset token has expired."""

    code = "expired_reset_token"


class InsufficientPermissionError(PermissionDeniedError):
    """The caller does not hold the required role or permission for this action."""

    code = "insufficient_permission"


# Telegram-linking exceptions (LinkedEmployeeNotFoundError, InvalidOTPError,
# ExpiredOTPError, TelegramAccountAlreadyLinkedError,
# TelegramAccountNotLinkedError) moved to apps/employees/domain/exceptions.py
# — Identity no longer has any Telegram-linking behavior to raise them from.
