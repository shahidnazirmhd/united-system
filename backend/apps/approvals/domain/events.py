"""Domain events published by the generic Approval Engine.

Published today with no subscriber required to exist yet at the point this
file is written — but unlike `apps.leave.domain.events`'s "publish now,
subscribe later" discipline, `ApprovalDecided` has an *immediate* real
subscriber: `apps.leave.interface.event_handlers.handle_approval_decided`,
registered in `apps/leave/apps.py`'s `ready()`. This is deliberate and is
the entire reason this engine can stay subject-agnostic while still
notifying Leave (or any future subject module) the moment a decision is
made: Approvals never imports Leave to call it directly (that would be
backwards — a generic engine must not depend on any specific consumer);
instead, any interested module subscribes to this event and filters on
`subject_type` itself. See
`shared_kernel/infrastructure/event_bus_impl.py`'s docstring, which
anticipated exactly this use case ("needed once Approvals/Notifications
subscribe to events raised by other modules" — here it's the reverse
direction, other modules subscribing to Approvals, which the same
Dependency-Inversion-via-EventBus mechanism supports equally well in
either direction).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from shared_kernel.domain.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ApprovalRequested(DomainEvent):
    """Published the moment a brand-new `ApprovalRequest` (and its first
    `ApprovalStep`) is created. No subscriber consumes this today — it
    exists for future Audit/Notifications concerns, exactly matching
    `apps.leave.domain.events.LeaveRequestApplied`'s "declared for a future
    subscriber" precedent. The real, immediate Telegram notification for
    this moment is sent synchronously (well, via Celery) by
    `ApprovalService` itself through `ApprovalNotificationPort`, not through
    this event — an event is for *reacting*, not for the engine's own
    required side effect of notifying the approver, which must not be
    optional/best-effort.
    """

    approval_request_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    level: int
    # Exactly one of these two is set — see
    # `apps.approvals.domain.value_objects.ApproverAssignment`. A
    # permission-based level (approver_employee_id is None) has no single
    # employee to carry here; that's also why no future subscriber can
    # assume this field is always populated.
    approver_employee_id: uuid.UUID | None
    approver_permission_code: str | None = None


@dataclass(frozen=True, kw_only=True)
class ApprovalStepAdvanced(DomainEvent):
    """Published when one level is approved and the chain resolver names a
    further level's approver — the request stays open, just at a new
    level. Declared for the same future-subscriber reasons as
    `ApprovalRequested`."""

    approval_request_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    new_level: int
    approver_employee_id: uuid.UUID | None
    approver_permission_code: str | None = None


@dataclass(frozen=True, kw_only=True)
class ApprovalDecided(DomainEvent):
    """Published exactly once per `ApprovalRequest`'s lifetime — when it
    reaches a final status, whether by a rejection at any level or an
    approval at the last level in the chain. `subject_type`/`subject_id`
    are what a subscriber filters on (see
    `apps.leave.interface.event_handlers.handle_approval_decided`, which
    ignores every event whose `subject_type != "leave.leave_request"`).
    """

    approval_request_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    final_status: str  # ApprovalStatus.APPROVED.value or ApprovalStatus.REJECTED.value
    decided_by_employee_id: uuid.UUID
    comments: str | None


@dataclass(frozen=True, kw_only=True)
class ApprovalRequestCancelled(DomainEvent):
    """Round 17 item 2 — published when `ApprovalService.cancel_for_subject`
    closes a still-open request because the subject module (e.g. Leave)
    cancelled the underlying record. Declared for the same future-subscriber
    reasons as `ApprovalRequested`/`ApprovalStepAdvanced` — no subscriber
    consumes this today; the subject module itself already knows it
    initiated the cancellation, so it has no need to react to its own event
    coming back around. Distinct from `ApprovalDecided` on purpose: this is
    never published by `decide()`, only by `cancel_for_subject`, keeping
    "an approver decided" and "the subject was withdrawn" separately
    observable in event history."""

    approval_request_id: uuid.UUID
    subject_type: str
    subject_id: uuid.UUID
    reason: str | None
