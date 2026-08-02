"""The core, fully generic Approval Engine service.

This is the one class every requirement from the Phase 9 brief is
implemented in: dynamic/future-ready approval levels, approve, reject,
approval comments, approval history, and approval status tracking. It has
zero knowledge of Leave, Attendance, or any other subject module — every
subject-specific fact (who approves level N, how to notify someone,
what an employee's display name is) arrives through a port
(`application/ports.py`) or is handed in as an opaque value
(`subject_type`/`subject_id`/`subject_summary`) by whichever module calls
`create_approval_request`.

Dynamic-levels mechanism (the brief's core architectural requirement,
"support multiple approval levels in the future without modifying the core
Approval Engine"): `ApprovalStep` rows are created lazily, one level at a
time.
  * `create_approval_request` asks the subject's registered
    `ApprovalChainResolverPort` for level 1's approver and creates exactly
    one step.
  * `decide` — on approval — asks the same resolver for
    `current_level + 1`'s approver. If one exists, a new step is created at
    that level and the request stays PENDING (now at the new level). If the
    resolver returns `None`, the chain is complete and the request is
    marked APPROVED.
  * `decide` — on rejection, at ANY level — ends the whole request
    immediately; no further level is ever consulted.

Nothing above changes when a subject module adds a second, third, or Nth
level tomorrow — that is entirely a change to that module's own
`ApprovalChainResolverPort` implementation (see
`apps.leave.infrastructure.leave_approval_chain_resolver`), never to this
class.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from dataclasses import replace

from apps.approvals.application.dtos import (
    ApprovalRequestResponse,
    ApprovalStepResponse,
    CancelApprovalRequestForSubjectRequest,
    CreateApprovalRequestRequest,
    DecideApprovalRequest,
)
from apps.approvals.application.mappers import approval_request_to_response
from apps.approvals.application.ports import ApprovalAuthorizationPort, ApprovalNotificationPort, EmployeeLookupPort
from apps.approvals.application.registry import ApprovalChainResolverRegistry
from apps.approvals.domain.entities import ApprovalRequest, ApprovalStep
from apps.approvals.domain.enums import ApprovalStatus, ApprovalStepStatus
from apps.approvals.domain.value_objects import ApproverAssignment
from apps.approvals.domain.exceptions import (
    ApprovalChannelNotAllowedError,
    ApprovalRequestNotFoundError,
    ApprovalRequestNotPendingError,
    ApprovalStepNotFoundError,
    NoApprovalChainResolverRegisteredError,
    NoApproverAvailableError,
    NotTheAssignedApproverError,
)
from apps.approvals.domain.repositories import ApprovalRequestRepository, ApprovalStepRepository
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.uuid7 import generate_uuid7

logger = logging.getLogger(__name__)

DECISION_APPROVE = "approve"
DECISION_REJECT = "reject"


class ApprovalService:
    def __init__(
        self,
        approval_request_repository: ApprovalRequestRepository,
        approval_step_repository: ApprovalStepRepository,
        chain_resolvers: ApprovalChainResolverRegistry,
        notifications: ApprovalNotificationPort,
        authorization: ApprovalAuthorizationPort,
        employee_lookup: EmployeeLookupPort,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        self._requests = approval_request_repository
        self._steps = approval_step_repository
        self._chain_resolvers = chain_resolvers
        self._notifications = notifications
        self._authz = authorization
        self._employees = employee_lookup
        self._uow = unit_of_work
        self._event_bus = event_bus

    # --- response enrichment (Approval Workflow Changes review round) ----
    def _enrich_step(self, step_response: ApprovalStepResponse) -> ApprovalStepResponse:
        """One `EmployeeLookupPort` call per step that has someone to name —
        bounded by however many steps one `ApprovalRequest` has (1-3 in
        practice), never by table size. Mirrors
        `apps.leave.application.services.leave_service.LeaveService
        ._enrich_with_employee_display`'s exact tradeoff.

        Approval Workflow Changes v2: prefers `decided_by_employee_id`
        (who actually clicked Approve/Reject) once the step is decided,
        falling back to `approver_employee_id` (who was originally
        assigned/referenced) while still pending — this is what makes
        "approved/rejected by X" correct even for a dual-mode or
        permission-based step decided by someone other than whoever was
        statically referenced (e.g. Leave's level 1 decided via the web by
        an `approvals.level1_approve` holder who isn't the manager). A
        step with neither set (a still-pending, non-dual-mode
        permission-based step, e.g. Leave's level 2 before anyone acts) is
        left untouched — there genuinely is no single employee to name yet."""
        display_employee_id = step_response.decided_by_employee_id or step_response.approver_employee_id
        if display_employee_id is None:
            return step_response
        display = self._employees.get_employee_display_info(display_employee_id)
        if display is None:
            return step_response
        full_name, employee_code = display
        return replace(step_response, approver_employee_name=full_name, approver_employee_code=employee_code)

    def _to_response(self, request: ApprovalRequest, steps: list[ApprovalStep]) -> ApprovalRequestResponse:
        """The one place every public method below builds its return value
        — guarantees `approver_employee_name`/`approver_employee_code` are
        always populated the same way, regardless of which read (or write)
        produced the response."""
        response = approval_request_to_response(request, steps=steps)
        return replace(response, steps=[self._enrich_step(s) for s in response.steps])

    # --- writes -----------------------------------------------------
    def create_approval_request(self, request: CreateApprovalRequestRequest) -> ApprovalRequestResponse:
        """Called directly (synchronously) by a subject module right after
        it creates the underlying record needing approval (e.g.
        `apps.leave.application.services.leave_request_service.LeaveRequestService.apply_leave`)
        — this is a required side effect, not best-effort: the caller is
        expected to run this inside the same `UnitOfWork`/transaction it
        used to create the subject record, so if no approver can be found,
        the whole operation (subject record included) rolls back together.
        """
        resolver = self._chain_resolvers.get(request.subject_type)
        if resolver is None:
            raise NoApprovalChainResolverRegisteredError(
                f"No approval chain resolver is registered for subject_type='{request.subject_type}'."
            )
        assignment = resolver.resolve_next_approver(
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            requested_by_employee_id=request.requested_by_employee_id,
            level=1,
        )
        if assignment is None:
            raise NoApproverAvailableError()

        approval_request = ApprovalRequest(
            id=generate_uuid7(),
            subject_type=request.subject_type,
            subject_id=request.subject_id,
            requested_by_employee_id=request.requested_by_employee_id,
            subject_summary=request.subject_summary,
            status=ApprovalStatus.PENDING,
            current_level=1,
        )
        step = ApprovalStep(
            id=generate_uuid7(),
            approval_request_id=approval_request.id,
            level=1,
            approver_employee_id=assignment.employee_id,
            approver_permission_code=assignment.permission_code,
            restricted_to_channel=assignment.restricted_to_channel,
            permission_required_for_channel=assignment.permission_required_for_channel,
        )
        with self._uow:
            created_request = self._requests.create(approval_request)
            created_step = self._steps.create(step)

        self._notify_approval_requested(created_request, created_step)
        from apps.approvals.domain.events import ApprovalRequested

        self._event_bus.publish(
            ApprovalRequested(
                approval_request_id=created_request.id,
                subject_type=created_request.subject_type,
                subject_id=created_request.subject_id,
                level=created_step.level,
                approver_employee_id=created_step.approver_employee_id,
                approver_permission_code=created_step.approver_permission_code,
            )
        )
        logger.info(
            "Approval request created: id=%s subject=%s:%s approver=%s (level 1)",
            created_request.id,
            created_request.subject_type,
            created_request.subject_id,
            created_step.approver_employee_id or f"permission:{created_step.approver_permission_code}",
        )
        return self._to_response(created_request, [created_step])

    def _notify_approval_requested(self, approval_request: ApprovalRequest, step: ApprovalStep) -> None:
        """Dispatches the "you have a pending approval" push — only when
        the step is assigned to one specific employee. A permission-based
        step has no single Telegram chat id to address (it may qualify
        several employees, or none yet); those employees discover it via
        the frontend's "My Pending Approvals" list instead, which resolves
        the caller's own permission codes at read time (see
        `list_pending_for_approver`)."""
        if step.approver_employee_id is None:
            return
        self._dispatch_after_commit(
            lambda: self._notifications.notify_approval_requested(
                approver_employee_id=step.approver_employee_id,
                subject_summary=approval_request.subject_summary,
                approval_request_id=approval_request.id,
                level=step.level,
            )
        )

    def _notify_requester_of_advance(
        self, approval_request: ApprovalRequest, next_assignment: ApproverAssignment, *, new_level: int
    ) -> None:
        """Leave review round: tells the ORIGINAL requester their request
        was just approved at a non-final level and has moved on — distinct
        from, and never a substitute for, `_publish_decision`'s
        `notify_decision_made`, which only fires once the chain actually
        concludes. Falls back to a generic message when the resolver didn't
        supply `requester_notification_message` (e.g. a future subject
        module that hasn't opted into this yet) so every multi-level chain
        still tells its requester *something* rather than going silent
        mid-chain."""
        message = next_assignment.requester_notification_message or (
            f"Your request has moved to level {new_level} for further approval."
        )
        self._dispatch_after_commit(
            lambda: self._notifications.notify_step_advanced(
                requested_by_employee_id=approval_request.requested_by_employee_id,
                subject_summary=approval_request.subject_summary,
                message=message,
                new_level=new_level,
                approval_request_id=approval_request.id,
            )
        )

    def cancel_for_subject(
        self, request: CancelApprovalRequestForSubjectRequest
    ) -> ApprovalRequestResponse | None:
        """Round 17 item 2 — closes the currently-open (PENDING) approval
        request for a subject that the calling module has just cancelled on
        its own side (e.g.
        `apps.leave.application.services.leave_request_service.LeaveRequestService.cancel_leave`)
        — a cancelled subject must never leave a PENDING approval request
        behind it that some approver could still act on.

        Idempotent no-op (returns `None`) if no PENDING approval request
        exists for this subject — either it was already fully decided
        (approved/rejected) before the subject was cancelled, in which case
        there is nothing open to close, or none was ever created for it at
        all. The calling module is expected to always call this on
        cancellation regardless of the subject's own prior state (see
        `LeaveRequestService.cancel_leave`), rather than pre-checking
        whether one exists — this method's own `get_pending_by_subject`
        lookup is that check.

        Deliberately a NEW terminal `ApprovalStatus.CANCELLED`/
        `ApprovalStepStatus.CANCELLED`, never `mark_rejected()`/`.reject()`
        — the calling module's own cancellation and a REJECTION are
        different actions with different meanings (one is the requester
        withdrawing, the other is an approver saying no) and must stay
        distinguishable in approval history (round 17 item 2's explicit
        requirement). Marking the request CANCELLED here is also what makes
        `decide()`'s own `status != PENDING` guard block any further
        approve/reject attempt against it — no changes to `decide()` itself
        were needed for that requirement.
        """
        approval_request = self._requests.get_pending_by_subject(
            subject_type=request.subject_type, subject_id=request.subject_id
        )
        if approval_request is None:
            return None

        cancelled_at = datetime.now(timezone.utc)
        current_step = self._steps.get_by_request_and_level(
            approval_request_id=approval_request.id, level=approval_request.current_level
        )
        cancelled_request = approval_request.mark_cancelled()
        with self._uow:
            # Also cancel the currently-open STEP, not just the request —
            # `list_pending_for_approver` filters on step status, so leaving
            # it PENDING would keep showing a phantom, no-longer-decidable
            # entry in an approver's own pending list even though the
            # request-level guard above already blocks deciding it.
            if current_step is not None and current_step.status == ApprovalStepStatus.PENDING:
                self._steps.update(current_step.cancel(decided_at=cancelled_at, comments=request.reason))
            saved_request = self._requests.update(cancelled_request)

        from apps.approvals.domain.events import ApprovalRequestCancelled

        self._event_bus.publish(
            ApprovalRequestCancelled(
                approval_request_id=saved_request.id,
                subject_type=saved_request.subject_type,
                subject_id=saved_request.subject_id,
                reason=request.reason,
            )
        )
        logger.info(
            "Approval request cancelled: id=%s subject=%s:%s (closed by subject module)",
            saved_request.id,
            saved_request.subject_type,
            saved_request.subject_id,
        )
        return self._to_response(saved_request, self._steps.list_by_request(approval_request_id=saved_request.id))

    def decide(self, request: DecideApprovalRequest) -> ApprovalRequestResponse:
        """Approve or reject the approval request's CURRENT level, on
        behalf of `request.acting_employee_id` — the caller (self-service
        REST view or Telegram-facing view) has already resolved whichever
        JWT/telegram_user_id identified the caller down to an employee id;
        this method itself enforces "you must be the approver assigned to
        the current level," not the interface layer (CODING_STANDARD.md:
        "no business logic in views").
        """
        approval_request = self._requests.get_by_id(request.approval_request_id)
        if approval_request is None:
            raise ApprovalRequestNotFoundError()
        if approval_request.status != ApprovalStatus.PENDING:
            raise ApprovalRequestNotPendingError(
                f"Approval request {approval_request.id} has already been '{approval_request.status.value}'."
            )

        step = self._steps.get_by_request_and_level(
            approval_request_id=approval_request.id, level=approval_request.current_level
        )
        if step is None:
            # Defensive only — create_approval_request/decide always create
            # the current level's step together with (or before) advancing
            # current_level, so this should be unreachable.
            raise ApprovalStepNotFoundError()
        if not step.is_decidable_via_channel(request.channel):
            # Checked BEFORE the identity check below — a wrong-channel
            # attempt is rejected regardless of whether the caller would
            # otherwise have been the right person (Approval Workflow
            # Changes review round; e.g. Leave's level 1/manager step is
            # `restricted_to_channel="telegram"`, so even the correct
            # manager gets this from the web REST surface).
            raise ApprovalChannelNotAllowedError(
                f"This approval step can only be decided via {step.restricted_to_channel}."
            )
        held_permission_codes = (
            self._authz.get_permission_codes_for_employee(request.acting_employee_id)
            if step.approver_permission_code is not None
            else frozenset()
        )
        if not step.is_decidable_by(
            acting_employee_id=request.acting_employee_id,
            held_permission_codes=held_permission_codes,
            channel=request.channel,
        ):
            raise NotTheAssignedApproverError()

        decided_at = datetime.now(timezone.utc)
        if request.decision == DECISION_REJECT:
            return self._reject(
                approval_request, step, decided_at=decided_at, comments=request.comments,
                acting_employee_id=request.acting_employee_id,
            )
        return self._approve(
            approval_request, step, decided_at=decided_at, comments=request.comments,
            acting_employee_id=request.acting_employee_id,
        )

    def _reject(
        self,
        approval_request: ApprovalRequest,
        step: ApprovalStep,
        *,
        decided_at: datetime,
        comments: str | None,
        acting_employee_id: uuid.UUID,
    ) -> ApprovalRequestResponse:
        decided_step = step.reject(decided_at=decided_at, decided_by_employee_id=acting_employee_id, comments=comments)
        rejected_request = approval_request.mark_rejected()
        with self._uow:
            saved_step = self._steps.update(decided_step)
            saved_request = self._requests.update(rejected_request)

        self._publish_decision(saved_request, decided_by_employee_id=acting_employee_id, comments=comments)
        logger.info(
            "Approval request rejected: id=%s subject=%s:%s level=%s by=%s",
            saved_request.id,
            saved_request.subject_type,
            saved_request.subject_id,
            saved_step.level,
            acting_employee_id,
        )
        return self._to_response(saved_request, self._steps.list_by_request(approval_request_id=saved_request.id))

    def _approve(
        self,
        approval_request: ApprovalRequest,
        step: ApprovalStep,
        *,
        decided_at: datetime,
        comments: str | None,
        acting_employee_id: uuid.UUID,
    ) -> ApprovalRequestResponse:
        decided_step = step.approve(decided_at=decided_at, decided_by_employee_id=acting_employee_id, comments=comments)

        resolver = self._chain_resolvers.get(approval_request.subject_type)
        if resolver is None:
            # Unreachable in practice (the resolver existed when this
            # request was created), but the registry is process-global
            # mutable state — defensive rather than assuming it can never
            # change mid-process.
            raise NoApprovalChainResolverRegisteredError(
                f"No approval chain resolver is registered for subject_type='{approval_request.subject_type}'."
            )
        next_level = approval_request.current_level + 1
        next_assignment = resolver.resolve_next_approver(
            subject_type=approval_request.subject_type,
            subject_id=approval_request.subject_id,
            requested_by_employee_id=approval_request.requested_by_employee_id,
            level=next_level,
        )

        if next_assignment is not None:
            # --- Dynamic levels: another level exists, keep the request open ---
            new_step = ApprovalStep(
                id=generate_uuid7(), approval_request_id=approval_request.id, level=next_level,
                approver_employee_id=next_assignment.employee_id,
                approver_permission_code=next_assignment.permission_code,
                restricted_to_channel=next_assignment.restricted_to_channel,
                permission_required_for_channel=next_assignment.permission_required_for_channel,
            )
            advanced_request = approval_request.advance_to_level(next_level)
            with self._uow:
                saved_step = self._steps.update(decided_step)
                created_step = self._steps.create(new_step)
                saved_request = self._requests.update(advanced_request)

            self._notify_approval_requested(saved_request, created_step)
            self._notify_requester_of_advance(saved_request, next_assignment, new_level=next_level)
            from apps.approvals.domain.events import ApprovalStepAdvanced

            self._event_bus.publish(
                ApprovalStepAdvanced(
                    approval_request_id=saved_request.id,
                    subject_type=saved_request.subject_type,
                    subject_id=saved_request.subject_id,
                    new_level=created_step.level,
                    approver_employee_id=created_step.approver_employee_id,
                    approver_permission_code=created_step.approver_permission_code,
                )
            )
            logger.info(
                "Approval request advanced: id=%s subject=%s:%s now at level=%s approver=%s",
                saved_request.id,
                saved_request.subject_type,
                saved_request.subject_id,
                created_step.level,
                created_step.approver_employee_id or f"permission:{created_step.approver_permission_code}",
            )
            return self._to_response(
                saved_request, self._steps.list_by_request(approval_request_id=saved_request.id)
            )

        # --- Chain complete: this was the last level ---
        approved_request = approval_request.mark_approved()
        with self._uow:
            saved_step = self._steps.update(decided_step)
            saved_request = self._requests.update(approved_request)

        self._publish_decision(saved_request, decided_by_employee_id=acting_employee_id, comments=comments)
        logger.info(
            "Approval request approved: id=%s subject=%s:%s final level=%s by=%s",
            saved_request.id,
            saved_request.subject_type,
            saved_request.subject_id,
            saved_step.level,
            acting_employee_id,
        )
        return self._to_response(saved_request, self._steps.list_by_request(approval_request_id=saved_request.id))

    def _publish_decision(
        self, saved_request: ApprovalRequest, *, decided_by_employee_id: uuid.UUID, comments: str | None
    ) -> None:
        self._dispatch_after_commit(
            lambda: self._notifications.notify_decision_made(
                requested_by_employee_id=saved_request.requested_by_employee_id,
                subject_summary=saved_request.subject_summary,
                final_status=saved_request.status.value,
                comments=comments,
                approval_request_id=saved_request.id,
            )
        )
        from apps.approvals.domain.events import ApprovalDecided

        self._event_bus.publish(
            ApprovalDecided(
                approval_request_id=saved_request.id,
                subject_type=saved_request.subject_type,
                subject_id=saved_request.subject_id,
                final_status=saved_request.status.value,
                decided_by_employee_id=decided_by_employee_id,
                comments=comments,
            )
        )

    def _dispatch_after_commit(self, callback) -> None:
        """Notifications (which dispatch a Celery task that calls out to
        the Telegram Gateway) must only fire once the transaction that
        created/updated the approval rows has actually committed — sending
        a Telegram message and then rolling back the corresponding database
        write would show the approver a request that no longer exists in
        the database. Delegated to the injected `UnitOfWork` (never a
        direct `django.db.transaction` import here — that would leak an
        infrastructure/framework concern into the application layer) —
        `DjangoUnitOfWork.on_commit` defers via Django's real mechanism in
        production, while a `FakeUnitOfWork` in unit tests just runs the
        callback immediately (see `UnitOfWork.on_commit`'s own docstring).
        """
        self._uow.on_commit(callback)

    # --- reads ------------------------------------------------------
    def get_detail(self, approval_request_id: uuid.UUID) -> ApprovalRequestResponse:
        """Approval status tracking / approval history for one request —
        every step ever reached, in level order, each carrying its own
        comments/decided_at."""
        approval_request = self._requests.get_by_id(approval_request_id)
        if approval_request is None:
            raise ApprovalRequestNotFoundError()
        steps = self._steps.list_by_request(approval_request_id=approval_request.id)
        return self._to_response(approval_request, steps)

    def list_pending_for_approver(
        self, approver_employee_id: uuid.UUID, *, channel: str | None = None
    ) -> list[ApprovalRequestResponse]:
        """Every approval request currently awaiting a decision from this
        employee — "My Pending Approvals" (self-service REST) and
        Telegram's `/pending_approvals`. Aggregates both assignment modes:
        steps assigned to this employee specifically, and permission-based
        steps this employee currently qualifies for (e.g. any
        `leave.manage_leave` holder sees every pending Leave HR-level step,
        not just one designated person's).

        `channel` (Approval Workflow Changes review round) — when supplied,
        a step this employee could otherwise act on is left OUT of the
        result entirely if it's restricted to a different channel (see
        `ApprovalStep.is_decidable_via_channel`) — e.g. an HR/Admin's
        web-only level-2 step never appears in their Telegram
        `/pending_approvals`, even if they'd otherwise qualify. `None` (the
        default) applies no filtering, preserving the original behavior for
        any caller that doesn't care.

        Approval Workflow Changes v2 — also re-checks `is_decidable_by(...,
        channel=channel)` for each candidate: the repository query below is
        deliberately a superset (identity OR permission match, channel-
        agnostic), which is no longer precise enough on its own now that a
        dual-mode step's actual per-channel authorization depends on WHICH
        of those two matched. E.g. a manager who does NOT hold
        `approvals.level1_approve` still matches the repository's identity
        clause for Leave's level 1, but must NOT see it in their WEB pending
        list (only in Telegram's) — `is_decidable_by` is what draws that
        line precisely; this refinement is a no-op for every plain
        single-mode step, since those were already exactly what the
        repository query matched."""
        held_permission_codes = self._authz.get_permission_codes_for_employee(approver_employee_id)
        pending_steps = self._steps.list_pending_for_approver(
            approver_employee_id=approver_employee_id, held_permission_codes=held_permission_codes
        )
        if channel is not None:
            pending_steps = [
                s
                for s in pending_steps
                if s.is_decidable_via_channel(channel)
                and s.is_decidable_by(
                    acting_employee_id=approver_employee_id,
                    held_permission_codes=held_permission_codes,
                    channel=channel,
                )
            ]
        responses: list[ApprovalRequestResponse] = []
        for step in pending_steps:
            approval_request = self._requests.get_by_id(step.approval_request_id)
            if approval_request is None:
                continue  # defensive only — a step never outlives its request
            responses.append(self._to_response(approval_request, [step]))
        return responses

    def list_by_subject(self, *, subject_type: str, subject_id: uuid.UUID) -> list[ApprovalRequestResponse]:
        """Every approval request ever raised for one subject (a Leave
        request that was, hypothetically, re-submitted would have more than
        one over time) — used by a subject module that wants to show its
        own detail view enriched with approval history."""
        requests = self._requests.list_by_subject(subject_type=subject_type, subject_id=subject_id)
        return [
            self._to_response(r, self._steps.list_by_request(approval_request_id=r.id))
            for r in requests
        ]
