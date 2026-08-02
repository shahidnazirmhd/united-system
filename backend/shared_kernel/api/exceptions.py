"""Base exception types raised by domain/application-layer code.

The custom DRF exception handler (exception_handler.py) knows how to
translate any DomainError subclass into the standard error envelope. No
module-specific exception should skip this base class — doing so would
force the interface layer to special-case it, which is exactly what "no
business logic in views" (CODING_STANDARD.md) rules out: a view should never
need its own knowledge of what a particular business exception means.
"""
from __future__ import annotations

import textwrap


def _first_paragraph(text: str) -> str:
    """Bugfix (round 16 item 1): `DomainError` used to fall back to
    `cls.__doc__` verbatim when a subclass is raised with no explicit
    message — fine for a short, single-sentence docstring, but many
    exception classes in this codebase document their full architectural
    reasoning in the SAME docstring, in paragraphs after the user-facing
    sentence (see e.g. `apps.leave.domain.exceptions
    .EmployeeNotEligibleForLeaveError`). Raising one of those with no
    explicit message dumped the entire multi-paragraph docstring —
    internal reasoning included — straight into the HTTP error envelope,
    which the HR web frontend then rendered verbatim as `error.message`
    (Telegram was insulated from this by its own `_FRIENDLY_MESSAGES`
    lookup table, but any code missing from that table fell through to a
    generic message instead). This helper takes only the first
    blank-line-delimited paragraph — by convention the user-facing
    sentence every exception in this codebase already leads with — and
    collapses its internal line wrapping into single spaces, so a
    docstring's own indentation/wrapping never leaks into the message
    text. Single-paragraph docstrings (the majority) are unaffected."""
    first_paragraph = textwrap.dedent(text).strip().split("\n\n", 1)[0]
    return " ".join(first_paragraph.split())


class DomainError(Exception):
    """Base class for all business-rule violations raised by domain/application code."""

    code: str = "domain_error"
    status_code: int = 400

    def __init__(self, message: str | None = None) -> None:
        resolved_message = message or (
            _first_paragraph(self.__class__.__doc__) if self.__class__.__doc__ else None
        ) or self.code
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
