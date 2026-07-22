"""Module-specific domain exceptions for Leave.

Every exception here extends one of shared_kernel's `DomainError` subclasses
(shared_kernel/api/exceptions.py) — `custom_exception_handler` translates
any of them into the standard error envelope automatically, so no view in
this module ever needs its own exception handling (CODING_STANDARD.md: "no
business logic in views" extends to error handling, not just the happy
path — matching apps/employees/domain/exceptions.py's precedent exactly).
"""
from __future__ import annotations

from shared_kernel.api.exceptions import ConflictError, NotFoundError, ValidationError


class LeaveTypeNotFoundError(NotFoundError):
    """No active leave type exists with this id."""

    code = "leave_type_not_found"


class LeaveBalanceNotFoundError(NotFoundError):
    """No leave balance record exists for this employee/leave type/year.

    Deliberately unused by `LeaveBalanceService.get_balance` (a missing
    balance row there is treated as "zero entitlement," not an error — see
    that method's docstring) — kept available for future callers (e.g. a
    strict admin "does this balance row exist" check) that genuinely want
    404 instead of a zeroed response.
    """

    code = "leave_balance_not_found"


class LeaveRequestNotFoundError(NotFoundError):
    """No leave request exists with this id."""

    code = "leave_request_not_found"


class LeaveEmployeeNotFoundError(NotFoundError):
    """The employee referenced by this leave operation does not exist.

    A distinct class from `apps.employees.domain.exceptions.EmployeeNotFoundError`
    on purpose — this module's domain layer must never import another
    module's domain layer (see `application/ports.py`'s `EmployeeLookupPort`
    for the only sanctioned way Leave learns anything about Employees).
    Same `code` string as Employees' own exception is intentional for a
    consistent API contract; the two classes remaining separate is what
    keeps the modules independent.
    """

    code = "employee_not_found"


class InsufficientLeaveBalanceError(ValidationError):
    """The employee does not have enough remaining balance for this leave type/year."""

    code = "insufficient_leave_balance"


class InvalidLeaveDateRangeError(ValidationError):
    """The requested end date is before the start date."""

    code = "invalid_leave_date_range"


class PastLeaveStartDateError(ValidationError):
    """The requested start date is in the past.

    Raised only when `settings.LEAVE_ALLOW_PAST_START_DATE` is `False` (the
    default) — see `application/services/leave_validation_service.py`.
    """

    code = "past_leave_start_date"


class OverlappingLeaveRequestError(ValidationError):
    """This employee already has a pending or approved leave request that
    overlaps these dates (any leave type — an employee cannot be on two
    kinds of leave at once)."""

    code = "overlapping_leave_request"


class DuplicateLeaveRequestError(ValidationError):
    """An identical leave request (same employee, leave type, and date
    range) is already pending or approved."""

    code = "duplicate_leave_request"


class LeaveRequestNotCancellableError(ConflictError):
    """The leave request cannot be cancelled from its current state.

    A `ConflictError` (409), not a `ValidationError` (422) — unlike the
    apply-time checks above, this is a state-machine rule about the
    resource's *own* current status (matching
    `apps.employees.domain.exceptions.InvalidEmployeeStatusTransitionError`'s
    reasoning for using the same base), not a validation of the caller's
    input against other data.
    """

    code = "leave_request_not_cancellable"


class LeaveRequestNotInPendingStateError(ConflictError):
    """`approve()`/`reject()` were called on a request that is not
    currently `PENDING` — the Approval module's extension point guard.
    """

    code = "leave_request_not_pending"


class LeaveRequestOwnershipError(ValidationError):
    """The caller is not permitted to act on a leave request that belongs
    to a different employee.

    A `ValidationError` (422) rather than `PermissionDeniedError` (403):
    this guards a data-ownership mismatch a self-service caller could only
    ever reach by guessing another employee's request id, not a genuine
    RBAC decision made by a permission class — see interface/viewsets.py.
    """

    code = "leave_request_ownership_mismatch"
