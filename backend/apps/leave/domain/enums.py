"""Domain enumerations for Leave.

Matches `shared_kernel.domain.enums.BaseEnum` — see that module's docstring
for why this is a plain `str`-mixin `Enum`, not Django's `TextChoices`.
`infrastructure/models.py` builds its Django field `choices=` from these
same members so the two can never drift apart, exactly like
`apps/employees/infrastructure/models.py` does with `EmployeeStatus`.
"""
from __future__ import annotations

from shared_kernel.domain.enums import BaseEnum


class LeaveRequestStatus(BaseEnum):
    """`DRAFT` exists as a value now even though nothing in this phase's
    API ever produces it — Apply Leave always creates `PENDING` directly
    (see LeaveRequestService.apply_leave's docstring for why: there is no
    "save for later" endpoint requested this phase). It is kept in the enum
    so the column's CHECK constraint and this type don't need to change the
    day a "save as draft" feature is actually built, only new code needs
    to start producing it.

    `PENDING` -> `APPROVED`/`REJECTED` are reachable only through
    `LeaveRequestService.approve()`/`reject()` — implemented and unit-tested
    this phase as the Approval module's extension point, but not wired to
    any REST endpoint, since "do not implement approval logic" means no
    caller exists yet, not that the transition itself shouldn't be ready.

    `PENDING`/`APPROVED` -> `CANCELLED` is reachable through
    `LeaveRequestService.cancel_leave()`, the one write-path this phase's
    API does expose beyond Apply.
    """

    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


#: Statuses that still "occupy" a date range for overlap/duplicate purposes
#: — you cannot hold two live requests (one pending, one already approved,
#: or two pending) over the same dates. Terminal, non-blocking outcomes
#: (`REJECTED`, `CANCELLED`) are deliberately excluded — those days were
#: never consumed, or were given back, and must not keep blocking new
#: requests over the same dates.
#:
#: NOT used for the sufficient-balance check — that check only sums
#: still-PENDING days (`LeaveRequestRepository.sum_pending_days`), because
#: `APPROVED` days are already reflected in `LeaveBalance.used_days`;
#: summing both here would double-count approved leave.
ACTIVE_LEAVE_REQUEST_STATUSES: tuple[LeaveRequestStatus, ...] = (
    LeaveRequestStatus.PENDING,
    LeaveRequestStatus.APPROVED,
)
