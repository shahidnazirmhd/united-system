"""Domain entities for the generic Approval Engine: `ApprovalRequest`
(aggregate root) and `ApprovalStep`.

Plain Python, no Django — matching every other module's domain layer
exactly (see apps/leave/domain/entities.py's docstring).

This module is deliberately subject-agnostic: neither entity has any
concept of "leave," "attendance," or any other business module. An
`ApprovalRequest` only knows `subject_type` (an opaque string like
"leave.leave_request") and `subject_id` (an opaque UUID) — it is the
*caller's* job (e.g. `apps.leave`) to know what those mean, never this
engine's. `subject_summary` is likewise an opaque, caller-supplied display
string, the same idiom `telegram_gateway/src/handlers/calendar_widget.py`
already uses for its `prompt`/`label` (a generic widget accepts an opaque
string from whoever is using it, rather than trying to know what it's
displaying).

Dynamic/future approval levels without ever modifying this engine: an
`ApprovalRequest` tracks only `current_level` (which `ApprovalStep` is the
active one right now); `ApprovalStep` rows are created lazily, one level at
a time, by `ApprovalService` — asking the subject module's own
`ApprovalChainResolverPort` implementation "who approves level N?" each
time a level is reached, rather than materializing every future level up
front. Adding a second level to Leave (or a first level to some future
module) is a change to that module's own resolver only, never to this
engine.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from apps.approvals.domain.enums import ApprovalStatus, ApprovalStepStatus
from shared_kernel.domain.base_entity import Entity


@dataclass(kw_only=True)
class ApprovalStep(Entity):
    # Logical reference to ApprovalRequest.id — same aggregate, real FK at
    # the ORM level (see infrastructure/models.py), unlike the
    # cross-module `subject_id`/employee-id fields below.
    approval_request_id: uuid.UUID
    level: int
    # Exactly one of the next two fields is ever set — see
    # `apps.approvals.domain.value_objects.ApproverAssignment`, which is
    # what a chain resolver returns and `ApprovalService` turns into one or
    # the other of these. `approver_employee_id` (logical reference to
    # apps.employees.domain.entities.Employee.id, plain UUID, never a
    # ForeignKey, matching every other module's identical discipline for
    # employee ids) is the original, single-employee assignment. Being
    # `None` here specifically means "assigned by permission instead" — it
    # never means "unassigned."
    approver_employee_id: uuid.UUID | None = None
    # A permission code (e.g. "approvals.level2_approve") — set instead of,
    # or (Approval Workflow Changes v2) alongside, `approver_employee_id`.
    # Alongside it means a DUAL-MODE step (see
    # `apps.approvals.domain.value_objects.ApproverAssignment
    # .for_employee_or_permission_by_channel`) — `permission_required_for_
    # channel` below says which one channel this permission actually governs
    # decision-making for; every other channel still goes by identity.
    # Instead of it (this field set, `approver_employee_id` null) is the
    # original single-employee-cohort mode (`ApproverAssignment
    # .for_permission`) — any employee currently holding this permission may
    # decide the step; `ApprovalService.decide` is what actually checks
    # that, via `is_decidable_by` below.
    approver_permission_code: str | None = None
    # Approval Workflow Changes review round: which channel
    # (`apps.approvals.domain.enums.ApprovalChannel.WEB`/`.TELEGRAM`) this
    # step may be decided from AT ALL, or `None` for "either, no
    # restriction" (the default, and the only behavior that existed before
    # this field) — copied verbatim from `ApproverAssignment
    # .restricted_to_channel` at the moment `ApprovalService` creates this
    # step. This engine never interprets the string itself beyond an
    # equality check in `is_decidable_via_channel`. Orthogonal to (and
    # checked before) `permission_required_for_channel` below, which governs
    # WHICH check applies on a given channel, not whether the channel is
    # allowed at all.
    restricted_to_channel: str | None = None
    # Approval Workflow Changes v2: only meaningful when both
    # `approver_employee_id` and `approver_permission_code` are set (a
    # dual-mode step). Names the one channel on which
    # `approver_permission_code` (not `approver_employee_id`) governs who
    # may decide — e.g. Leave's level 1 sets this to
    # `ApprovalChannel.WEB.value`, so the HR web system is controlled purely
    # by holding `approvals.level1_approve`, while Telegram remains governed
    # by literally being the assigned manager. See `is_decidable_by`.
    permission_required_for_channel: str | None = None
    # Approval Workflow Changes v2: which employee actually clicked
    # Approve/Reject — distinct from `approver_employee_id` (who was
    # originally, statically assigned/referenced). Always equal to
    # `approver_employee_id` for a plain single-employee step (only that one
    # person could ever decide it), but may differ for a permission-based or
    # dual-mode step, where more than one employee could qualify (e.g.
    # Leave's level 1 decided via the web by an `approvals.level1_approve`
    # holder who isn't the manager). `None` until decided. This is what lets
    # `ApprovalService` show "approved/rejected by <actual decider's name>"
    # correctly for every step, not just single-employee ones.
    decided_by_employee_id: uuid.UUID | None = None
    status: ApprovalStepStatus = ApprovalStepStatus.PENDING
    comments: str | None = None
    decided_at: datetime | None = None

    def is_decidable_by(
        self, *, acting_employee_id: uuid.UUID, held_permission_codes: frozenset[str], channel: str
    ) -> bool:
        """Whether `acting_employee_id` is allowed to decide this step right
        now, from `channel` — the one rule `ApprovalService.decide` enforces
        before letting anyone approve/reject (called only after
        `is_decidable_via_channel` has already confirmed the channel is
        allowed at all). `held_permission_codes` is only ever consulted for
        a permission-based or dual-mode step; a plain single-employee step
        never needs it.

        Dual-mode (Approval Workflow Changes v2 — both
        `approver_employee_id` and `approver_permission_code` set):
        `channel == permission_required_for_channel` switches the check to
        "does the caller hold `approver_permission_code`," ignoring identity
        entirely, even for the originally-assigned employee — e.g. Leave's
        level 1 on the web channel requires `approvals.level1_approve`, full
        stop, whether or not the caller is the manager. Every OTHER channel
        for a dual-mode step still requires being `approver_employee_id`
        exactly, ignoring permissions entirely — e.g. Leave's level 1 via
        Telegram still requires being the manager, even if some other
        employee also holds the permission.
        """
        if self.approver_employee_id is not None and self.approver_permission_code is not None:
            if channel == self.permission_required_for_channel:
                return self.approver_permission_code in held_permission_codes
            return self.approver_employee_id == acting_employee_id
        if self.approver_employee_id is not None:
            return self.approver_employee_id == acting_employee_id
        if self.approver_permission_code is not None:
            return self.approver_permission_code in held_permission_codes
        return False  # unreachable in practice — a step always has at least one assignment mode

    def is_decidable_via_channel(self, channel: str) -> bool:
        """Whether this step may be decided from `channel` at all — checked
        by `ApprovalService.decide` (and used to filter
        `list_pending_for_approver`'s results) independently of, and before,
        `is_decidable_by`'s identity/permission check above. `restricted_to_
        channel is None` means "no restriction," so this is always `True`
        for any step a subject module's resolver didn't opt into
        restricting — including every dual-mode step, which is by
        definition decidable from every channel (just via a different check
        per channel, not a smaller set of allowed channels)."""
        return self.restricted_to_channel is None or self.restricted_to_channel == channel

    def approve(
        self, *, decided_at: datetime, decided_by_employee_id: uuid.UUID, comments: str | None = None
    ) -> "ApprovalStep":
        from apps.approvals.domain.exceptions import ApprovalStepNotPendingError

        if self.status != ApprovalStepStatus.PENDING:
            raise ApprovalStepNotPendingError(
                f"Approval step {self.id} (level {self.level}) cannot be decided again "
                f"— it is already '{self.status.value}'."
            )
        return ApprovalStep(
            id=self.id,
            approval_request_id=self.approval_request_id,
            level=self.level,
            approver_employee_id=self.approver_employee_id,
            approver_permission_code=self.approver_permission_code,
            restricted_to_channel=self.restricted_to_channel,
            permission_required_for_channel=self.permission_required_for_channel,
            decided_by_employee_id=decided_by_employee_id,
            status=ApprovalStepStatus.APPROVED,
            comments=comments,
            decided_at=decided_at,
        )

    def reject(
        self, *, decided_at: datetime, decided_by_employee_id: uuid.UUID, comments: str | None = None
    ) -> "ApprovalStep":
        from apps.approvals.domain.exceptions import ApprovalStepNotPendingError

        if self.status != ApprovalStepStatus.PENDING:
            raise ApprovalStepNotPendingError(
                f"Approval step {self.id} (level {self.level}) cannot be decided again "
                f"— it is already '{self.status.value}'."
            )
        return ApprovalStep(
            id=self.id,
            approval_request_id=self.approval_request_id,
            level=self.level,
            approver_employee_id=self.approver_employee_id,
            approver_permission_code=self.approver_permission_code,
            restricted_to_channel=self.restricted_to_channel,
            permission_required_for_channel=self.permission_required_for_channel,
            decided_by_employee_id=decided_by_employee_id,
            status=ApprovalStepStatus.REJECTED,
            comments=comments,
            decided_at=decided_at,
        )

    def cancel(self, *, decided_at: datetime, comments: str | None = None) -> "ApprovalStep":
        """Round 17 item 2 — closes this still-open step because the SUBJECT
        module cancelled the underlying request, not because anyone
        approved/rejected it. `decided_by_employee_id` is deliberately left
        `None` (unlike `approve`/`reject`): nobody decided this step, it was
        closed as a side effect of the subject's own cancellation — see
        `ApprovalService.cancel_for_subject`, the only caller."""
        from apps.approvals.domain.exceptions import ApprovalStepNotPendingError

        if self.status != ApprovalStepStatus.PENDING:
            raise ApprovalStepNotPendingError(
                f"Approval step {self.id} (level {self.level}) cannot be cancelled "
                f"— it is already '{self.status.value}'."
            )
        return ApprovalStep(
            id=self.id,
            approval_request_id=self.approval_request_id,
            level=self.level,
            approver_employee_id=self.approver_employee_id,
            approver_permission_code=self.approver_permission_code,
            restricted_to_channel=self.restricted_to_channel,
            permission_required_for_channel=self.permission_required_for_channel,
            decided_by_employee_id=None,
            status=ApprovalStepStatus.CANCELLED,
            comments=comments,
            decided_at=decided_at,
        )


@dataclass(kw_only=True)
class ApprovalRequest(Entity):
    # Opaque to this engine — e.g. "leave.leave_request". A dot-separated
    # "<module>.<entity>" convention is recommended (see
    # apps.leave.infrastructure.leave_approval_chain_resolver's usage) but
    # not enforced here; this engine never parses or switches on it.
    subject_type: str
    # Opaque to this engine — the subject module's own primary key.
    subject_id: uuid.UUID
    # Logical reference to apps.employees.domain.entities.Employee.id — the
    # employee who submitted the underlying request (Leave's applicant,
    # a future module's requester, ...).
    requested_by_employee_id: uuid.UUID
    # Caller-supplied opaque display string — see this module's docstring.
    # Never re-derived or parsed by this engine; only ever stored and
    # handed back verbatim (to a notification port, to a REST read).
    subject_summary: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    current_level: int = 1

    def advance_to_level(self, level: int) -> "ApprovalRequest":
        """Called when the current level is approved and the subject
        module's chain resolver names another approver for `level` — the
        request stays `PENDING` overall, just at a new active level."""
        from apps.approvals.domain.exceptions import ApprovalRequestNotPendingError

        if self.status != ApprovalStatus.PENDING:
            raise ApprovalRequestNotPendingError(
                f"Approval request {self.id} cannot advance levels — it is already '{self.status.value}'."
            )
        return ApprovalRequest(
            id=self.id,
            subject_type=self.subject_type,
            subject_id=self.subject_id,
            requested_by_employee_id=self.requested_by_employee_id,
            subject_summary=self.subject_summary,
            status=ApprovalStatus.PENDING,
            current_level=level,
        )

    def mark_approved(self) -> "ApprovalRequest":
        """Called when the current level is approved and the chain
        resolver reports no further level — the chain is complete."""
        from apps.approvals.domain.exceptions import ApprovalRequestNotPendingError

        if self.status != ApprovalStatus.PENDING:
            raise ApprovalRequestNotPendingError(
                f"Approval request {self.id} cannot be approved — it is already '{self.status.value}'."
            )
        return ApprovalRequest(
            id=self.id,
            subject_type=self.subject_type,
            subject_id=self.subject_id,
            requested_by_employee_id=self.requested_by_employee_id,
            subject_summary=self.subject_summary,
            status=ApprovalStatus.APPROVED,
            current_level=self.current_level,
        )

    def mark_rejected(self) -> "ApprovalRequest":
        """Rejection at ANY level ends the whole request — there is no
        "reject at level 2, keep level 1's approval meaningful" concept;
        one rejection anywhere in the chain is final."""
        from apps.approvals.domain.exceptions import ApprovalRequestNotPendingError

        if self.status != ApprovalStatus.PENDING:
            raise ApprovalRequestNotPendingError(
                f"Approval request {self.id} cannot be rejected — it is already '{self.status.value}'."
            )
        return ApprovalRequest(
            id=self.id,
            subject_type=self.subject_type,
            subject_id=self.subject_id,
            requested_by_employee_id=self.requested_by_employee_id,
            subject_summary=self.subject_summary,
            status=ApprovalStatus.REJECTED,
            current_level=self.current_level,
        )

    def mark_cancelled(self) -> "ApprovalRequest":
        """Round 17 item 2 — closes this request because the SUBJECT module
        (e.g. Leave) cancelled the underlying record it was raised for, at
        ANY level, the same "final regardless of level" shape as
        `mark_rejected` above. Deliberately a distinct terminal status from
        `REJECTED`: a rejection is an approver's decision, a cancellation is
        the requester withdrawing — these must stay distinguishable in
        approval history (see `ApprovalService.cancel_for_subject`)."""
        from apps.approvals.domain.exceptions import ApprovalRequestNotPendingError

        if self.status != ApprovalStatus.PENDING:
            raise ApprovalRequestNotPendingError(
                f"Approval request {self.id} cannot be cancelled — it is already '{self.status.value}'."
            )
        return ApprovalRequest(
            id=self.id,
            subject_type=self.subject_type,
            subject_id=self.subject_id,
            requested_by_employee_id=self.requested_by_employee_id,
            subject_summary=self.subject_summary,
            status=ApprovalStatus.CANCELLED,
            current_level=self.current_level,
        )
