"""Domain enumerations for the generic Approval Engine.

Matches `shared_kernel.domain.enums.BaseEnum` exactly — see that module's
docstring for why this is a plain `str`-mixin `Enum`, not Django's
`TextChoices`. `infrastructure/models.py` builds its Django field
`choices=` from these same members so the two can never drift apart,
matching every other module's identical discipline.
"""
from __future__ import annotations

from shared_kernel.domain.enums import BaseEnum


class ApprovalStatus(BaseEnum):
    """Overall status of an `ApprovalRequest` (the aggregate root).

    `PENDING` covers every level of a multi-level chain — an
    `ApprovalRequest` only ever leaves `PENDING` once either (a) some level
    rejects it, or (b) the last level in the chain approves it (the chain
    resolver returns no further approver — see
    `application/services/approval_service.py`). There is deliberately no
    per-level status on this entity itself; that lives on `ApprovalStep`.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    # Round 17 item 2 — the SUBJECT module (e.g. Leave) closed this request
    # because the underlying subject itself was cancelled, not because any
    # approver rejected it. Deliberately distinct from `REJECTED`: those are
    # different actions with different meanings and must stay
    # distinguishable in approval history (see
    # `ApprovalService.cancel_for_subject`'s docstring). Once a request
    # reaches this status, `decide()`'s existing `status != PENDING` guard
    # blocks any further approve/reject attempt against it, with no changes
    # to `decide()` itself needed.
    CANCELLED = "cancelled"


class ApprovalStepStatus(BaseEnum):
    """Status of a single level's `ApprovalStep`.

    Steps are created lazily, one level at a time (see
    `ApprovalService.create_approval_request`/`decide` — the mechanism that
    lets this engine support an arbitrary number of future levels without
    ever being modified itself) — there is intentionally no `SKIPPED`
    member: a level that will never be reached simply never gets an
    `ApprovalStep` row created for it at all.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    # Round 17 item 2 — mirrors `ApprovalStatus.CANCELLED` at the step level:
    # set on the currently-open step when `ApprovalService.cancel_for_subject`
    # closes the whole request, so it also drops out of
    # `list_pending_for_approver` (which filters on step status), not just
    # the request-level read.
    CANCELLED = "cancelled"


class ApprovalChannel(BaseEnum):
    """Which interface a `decide()` call (or a "pending for approver" read)
    arrived through — `WEB` (the JWT-authenticated self-service/HR REST
    surface) or `TELEGRAM` (the Gateway-facing surface,
    `HasInternalServiceKey`).

    Orthogonal to *who* may decide a step (`approver_employee_id`/
    `approver_permission_code`) — this is *where* they're allowed to do it
    from. Set per-step, at step-creation time, via
    `ApproverAssignment.restricted_to_channel` (see that value object's
    docstring for the full "Approval Workflow Changes" review-round
    reasoning) — `None` on a step means "no restriction," which is the
    default and preserves the original, channel-agnostic behavior for every
    assignment that doesn't care. This engine itself has no opinion on which
    level of which subject module should be restricted to which channel;
    that decision belongs entirely to the subject module's own
    `ApprovalChainResolverPort` implementation (see
    `apps.leave.infrastructure.leave_approval_chain_resolver` for the first,
    and so far only, resolver that actually sets this).
    """

    WEB = "web"
    TELEGRAM = "telegram"
