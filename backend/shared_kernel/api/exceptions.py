"""Base exception types raised by domain/application-layer code.

The custom DRF exception handler (exception_handler.py) knows how to
translate any DomainError subclass into the standard error envelope. No
module-specific exception should skip this base class — doing so would
force the interface layer to special-case it, which is exactly what "no
business logic in views" (CODING_STANDARD.md) rules out: a view should never
need its own knowledge of what a particular business exception means.
"""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all business-rule violations raised by domain/application code."""

    code: str = "domain_error"
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        resolved_message = message or self.__class__.__doc__ or self.code
        super().__init__(resolved_message)
        self.message = resolved_message


class NotFoundError(DomainError):
    """The requested resource does not exist."""

    code = "not_found"
    status_code = 404


class ValidationError(DomainError):
    """The request failed a business validation rule."""

    code = "validation_error"
    status_code = 422


class PermissionDeniedError(DomainError):
    """The caller is not permitted to perform this action."""

    code = "permission_denied"
    status_code = 403


class ConflictError(DomainError):
    """The requested action conflicts with the current state of the resource."""

    code = "conflict"
    status_code = 409


class InvalidStateTransitionError(ConflictError):
    """The requested action is not valid from the resource's current state.

    A generic base for state-machine-shaped rules (e.g. Employee's
    activate/deactivate — see apps/employees/domain/exceptions.py) — a
    module raises its own subclass with a specific `code`/message rather
    than this class directly, matching the pattern already established for
    every other shared_kernel exception base.
    """

    code = "invalid_state_transition"
