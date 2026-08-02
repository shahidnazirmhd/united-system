"""Module-specific domain exceptions for the generic Approval Engine.

Every exception here extends one of shared_kernel's `DomainError` subclasses
(shared_kernel/api/exceptions.py) — `custom_exception_handler` translates
any of them into the standard error envelope automatically, so no view in
this module ever needs its own exception handling (CODING_STANDARD.md: "no
business logic in views" extends to error handling, matching every other
module's identical discipline).

None of these exceptions know anything about Leave, Attendance, or any
other subject module — they are phrased entirely in terms of this engine's
own vocabulary (approval requests, steps, approvers, chain resolvers).
"""
from __future__ import annotations

from shared_kernel.api.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationError


class ApprovalCallerNotAnEmployeeError(NotFoundError):
    """Your account is not linked to an employee record, so this approval
    cannot be processed. Please contact HR to link your account to an
    employee record.

    Round 17 item 1 bugfix: this docstring used to lead with "The calling
    principal is not linked to any employee record." — accurate but
    internal-jargon phrasing ("the calling principal") that `DomainError`'s
    `_first_paragraph` extraction (shared_kernel/api/exceptions.py) then
    surfaced verbatim as `error.message` to the HR web frontend
    (ApprovalsPage.tsx's `onError: (error) => setSubmitError(error.message)`)
    whenever a User with no linked Employee tried to decide (approve/reject)
    an approval — e.g. a pure Admin account with `approvals.level2_approve`
    but no Employee record of their own. The wording above is intentional —
    it is shown to the caller verbatim, matching the convention established
    by `apps.leave.domain.exceptions.NoManagerAssignedError`.

    A distinct class from `apps.employees.domain.exceptions.EmployeeNotFoundError`
    and `apps.leave.domain.exceptions.LeaveEmployeeNotFoundError` on
    purpose — this module's domain layer must never import another
    module's domain layer (see `application/ports.py`'s `EmployeeLookupPort`
    for the only sanctioned way this module learns anything about
    Employees). Same `code` string as those two is intentional for a
    consistent API contract; the three classes remaining separate is what
    keeps every module independent.
    """

    code = "employee_not_found"


class ApprovalRequestNotFoundError(NotFoundError):
    """No approval request exists with this id."""

    code = "approval_request_not_found"


class ApprovalStepNotFoundError(NotFoundError):
    """No approval step exists at the current level for this approval request."""

    code = "approval_step_not_found"


class NoApprovalChainResolverRegisteredError(ValidationError):
    """No approval chain resolver is registered for this subject type.

    Raised only if a subject module calls `create_approval_request` without
    first registering its `ApprovalChainResolverPort` implementation in
    `application/registry.py`'s `chain_resolver_registry` (see
    `apps.leave.apps.py`'s `ready()` for the expected registration pattern)
    — a programming error in the calling module, not a runtime business
    condition an end user can trigger.
    """

    code = "no_approval_chain_resolver_registered"


class NoApproverAvailableError(ValidationError):
    """No approver could be resolved for this request; it cannot be
    submitted for approval.

    Raised when a subject module's chain resolver returns `None` for level
    1 (no approver at all, e.g. Leave's employee has no manager) —
    ordinarily prevented upstream by the subject module's own validation
    (see `apps.leave.domain.exceptions.NoManagerAssignedError`), so this is
    a defensive guard inside the generic engine itself, never the
    user-facing error an employee actually sees.
    """

    code = "no_approver_available"


class ApprovalRequestNotPendingError(ConflictError):
    """This approval request has already been fully decided (approved or
    rejected) and can no longer be acted on."""

    code = "approval_request_not_pending"


class ApprovalStepNotPendingError(ConflictError):
    """This approval step has already been decided."""

    code = "approval_step_not_pending"


class NotTheAssignedApproverError(PermissionDeniedError):
    """You are not the approver assigned to the current level of this
    approval request."""

    code = "not_the_assigned_approver"


class ApprovalChannelNotAllowedError(PermissionDeniedError):
    """This approval step may not be decided from the channel the caller
    used (e.g. a level restricted to Telegram, attempted via the web REST
    surface, or vice versa).

    Checked before `NotTheAssignedApproverError` above — a wrong-channel
    attempt is rejected regardless of whether the caller would otherwise
    have been the right person, since "you can't do this from here at all"
    is the more fundamental gate. See
    `apps.approvals.domain.value_objects.ApproverAssignment
    .restricted_to_channel`'s docstring for why this engine enforces an
    opaque channel string without ever knowing what "Telegram" or "the HR
    system" means.
    """

    code = "approval_channel_not_allowed"
