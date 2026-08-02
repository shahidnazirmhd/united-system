"""Value objects for the generic Approval Engine.

`ApproverAssignment` is what an `ApprovalChainResolverPort` implementation
returns instead of a bare `uuid.UUID` — a level's approver is now either one
specific employee (unchanged behavior, e.g. "the applicant's manager") OR
"any employee currently holding this permission code" (new capability,
added so a subject module can assign a level to a whole role/permission
cohort — e.g. Leave's HR/Admin level — without the engine ever needing to
know how many people that resolves to, or who they are, until someone
actually acts).

Exactly one of `employee_id`/`permission_code` is ever set — enforced in
`__post_init__` so a malformed assignment fails at the point a resolver
constructs it, not later when `ApprovalService` tries to use it. This is
deliberately a frozen dataclass (not a raw tuple/dict) so both the intent
("this is a single-employee assignment" vs "this is a permission-based
assignment") and the invariant are explicit at every call site — matching
this codebase's general preference for small, self-validating value objects
over primitive shapes (see `apps.identity.domain.value_objects.Email` for
the same idiom elsewhere).

`requester_notification_message` (Leave review round) is a THIRD, always-
optional field, orthogonal to the employee-vs-permission choice above: an
opaque, subject-supplied sentence to push to the ORIGINAL REQUESTER the
moment this assignment becomes the request's current level as a result of
the *previous* level being approved (never sent for a level-1 assignment,
since that's returned at creation time, before anyone has approved
anything). This is exactly the same "opaque string the engine relays
without interpreting" pattern `subject_summary` already established —
`ApprovalService` never inspects or generates this text itself, it only
forwards whatever the resolver supplied (see
`ApprovalNotificationPort.notify_step_advanced`), which is what keeps the
engine subject-agnostic even though the review requirement asked for
very subject-specific wording ("Your manager has approved your leave
request. It is now awaiting HR processing.") — that sentence lives in
`apps.leave.infrastructure.leave_approval_chain_resolver`, not here.

`restricted_to_channel` (Approval Workflow Changes review round) is a
FOURTH, always-optional field, also orthogonal to the other three: which
interface (`apps.approvals.domain.enums.ApprovalChannel.WEB`/`.TELEGRAM`)
this assignment may be decided from, or `None` for "either, no
restriction" (the default, and the only behavior that existed before this
field). `ApprovalService.decide()` only ever compares this opaque string
against whichever channel the caller's own view supplied, exactly the same
"resolver decides the fact, engine only enforces it" shape
`requester_notification_message` already established.

`permission_required_for_channel` (Approval Workflow Changes v2 — "ignore
the Telegram-only restriction on level 1, gate the HR system by
permission instead") is a FIFTH, always-optional field enabling a new,
fully generic DUAL-MODE assignment: both `employee_id` AND
`permission_code` set simultaneously (via `for_employee_or_permission_by_channel`
below), with `permission_required_for_channel` saying which ONE channel's
decision is governed by `permission_code` instead of `employee_id`. Every
other channel still requires being `employee_id` specifically. This is
exactly Leave's new level 1: the applicant's manager (`employee_id`) can
still decide via Telegram purely by being that manager (identity check,
unchanged since Phase 9); on the web HR system
(`permission_required_for_channel=ApprovalChannel.WEB.value`), any
employee holding `approvals.level1_approve` (`permission_code`) may decide
instead — whether or not they are literally the manager. Deliberately NOT
combined with `restricted_to_channel` on the same assignment — a dual-mode
assignment is, by construction, decidable from every channel, just via a
different check depending on which one; see `ApprovalStep.is_decidable_by`
for the exact enforcement, and `apps.leave.infrastructure
.leave_approval_chain_resolver` for the concrete usage.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class ApproverAssignment:
    employee_id: uuid.UUID | None = None
    permission_code: str | None = None
    requester_notification_message: str | None = None
    restricted_to_channel: str | None = None
    permission_required_for_channel: str | None = None

    def __post_init__(self) -> None:
        if self.employee_id is None and self.permission_code is None:
            raise ValueError(
                "ApproverAssignment must set at least one of employee_id or permission_code."
            )
        if self.permission_required_for_channel is not None and (
            self.employee_id is None or self.permission_code is None
        ):
            raise ValueError(
                "permission_required_for_channel only makes sense on a dual-mode assignment — "
                "construct it via for_employee_or_permission_by_channel, which sets both "
                "employee_id and permission_code."
            )

    @classmethod
    def for_employee(
        cls,
        employee_id: uuid.UUID,
        *,
        requester_notification_message: str | None = None,
        restricted_to_channel: str | None = None,
    ) -> "ApproverAssignment":
        """A level assigned to one specific, already-known employee — e.g.
        Leave's level 1 (the applicant's manager). Behaves exactly as every
        approval level did before permission-based assignment existed."""
        return cls(
            employee_id=employee_id,
            requester_notification_message=requester_notification_message,
            restricted_to_channel=restricted_to_channel,
        )

    @classmethod
    def for_permission(
        cls,
        permission_code: str,
        *,
        requester_notification_message: str | None = None,
        restricted_to_channel: str | None = None,
    ) -> "ApproverAssignment":
        """A level assigned to whichever employee(s) currently hold
        `permission_code` — e.g. Leave's level 2 (`approvals.level2_approve`).
        Any qualifying employee can decide it; whoever acts first wins (the
        usual `ApprovalStepNotPendingError` guard prevents a second decide).
        No single employee is notified via Telegram for this kind of
        assignment (there is no one chat id to address) — qualifying
        employees discover it via the frontend's "My Pending Approvals",
        which resolves the current caller's permission codes at read time."""
        return cls(
            permission_code=permission_code,
            requester_notification_message=requester_notification_message,
            restricted_to_channel=restricted_to_channel,
        )

    @classmethod
    def for_employee_or_permission_by_channel(
        cls,
        *,
        employee_id: uuid.UUID,
        permission_code: str,
        permission_required_for_channel: str,
        requester_notification_message: str | None = None,
    ) -> "ApproverAssignment":
        """Dual-mode assignment (Approval Workflow Changes v2): decidable
        by `employee_id` from any channel EXCEPT
        `permission_required_for_channel`; from that one channel, decidable
        instead by any employee holding `permission_code`, whether or not
        they are `employee_id`. E.g. Leave's level 1 — see this module's
        docstring for the full reasoning and `ApprovalStep.is_decidable_by`
        for the exact per-channel enforcement this produces."""
        return cls(
            employee_id=employee_id,
            permission_code=permission_code,
            permission_required_for_channel=permission_required_for_channel,
            requester_notification_message=requester_notification_message,
        )

    @property
    def is_permission_based(self) -> bool:
        return self.permission_code is not None

    @property
    def is_dual_mode(self) -> bool:
        """Both an identity AND a permission code are set — see
        `for_employee_or_permission_by_channel`."""
        return self.employee_id is not None and self.permission_code is not None
