"""Write side (Apply/Cancel + the Approval extension point) and detail/
history reads for Leave requests.

Extends `BaseService[LeaveRequest]` for `get_by_id`/`list` (View Leave
Request Details / View Leave History — genuinely uniform reads, exactly
the shape `BaseService` was built for) but bypasses `BaseService.create`/
`update` entirely for `apply_leave`/`cancel_leave`/`approve`/`reject` — a
leave application is not a plain-CRUD create (it runs a multi-step
validation pipeline via `LeaveValidationService` and touches
`LeaveBalanceService` too), matching exactly the same judgment call
`EmployeeCommandService.activate_employee`/`deactivate_employee` already
made for non-CRUD state transitions (see this phase's architecture notes).
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from apps.leave.application.dtos import (
    ApplyLeaveRequest,
    ApproveLeaveRequest,
    CancelLeaveRequest,
    LeaveRequestResponse,
    RejectLeaveRequest,
)
from apps.leave.application.mappers import leave_request_to_response
from apps.leave.application.ports import (
    ApprovalRequestPort,
    EmployeeStatusPort,
    HolidayLookupPort,
    LeaveNotificationPort,
    SettingsLookupPort,
)
from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.application.services.leave_validation_service import LeaveValidationService
from apps.leave.domain.entities import LeaveRequest
from apps.leave.domain.events import (
    LeaveRequestApplied,
    LeaveRequestApproved,
    LeaveRequestCancelled,
    LeaveRequestRejected,
)
from apps.leave.domain.exceptions import LeaveRequestNotFoundError, LeaveRequestOwnershipError
from apps.leave.domain.repositories import LeaveRequestRepository, LeaveTypeRepository
from apps.leave.domain.working_days_calculator import calculate_working_days
from shared_kernel.application.base_service import BaseService
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.uuid7 import generate_uuid7

logger = logging.getLogger(__name__)


class LeaveRequestService(BaseService[LeaveRequest]):
    not_found_exception = LeaveRequestNotFoundError

    def __init__(
        self,
        leave_request_repository: LeaveRequestRepository,
        leave_type_repository: LeaveTypeRepository,
        validation_service: LeaveValidationService,
        balance_service: LeaveBalanceService,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
        approval_requests: ApprovalRequestPort,
        settings_lookup: SettingsLookupPort,
        holiday_lookup: HolidayLookupPort,
        employee_status: EmployeeStatusPort,
        notifications: LeaveNotificationPort,
    ) -> None:
        super().__init__(repository=leave_request_repository, unit_of_work=unit_of_work, event_bus=event_bus)
        self._requests = leave_request_repository
        self._leave_types = leave_type_repository
        self._validate = validation_service
        self._balances = balance_service
        self._approvals = approval_requests
        # Round 14 items 6/8 — immediate (same-day) employee status
        # transitions at approve/cancel time; the daily reconciliation
        # Celery task (tasks.py) handles future-dated approved leaves
        # whose start/end date arrives later. See _sync_status_on_approve/
        # _sync_status_on_cancel below.
        self._employee_status = employee_status
        # Round 14 item 6 — resolve the current week-off/holiday
        # configuration at apply time only (see
        # domain/working_days_calculator.py's docstring for why the domain
        # layer itself never reaches into these two modules directly).
        self._settings = settings_lookup
        self._holidays = holiday_lookup
        # Round 15 item 6 — see apps.leave.application.ports
        # .LeaveNotificationPort's docstring for why this is Leave's own
        # channel, not a reuse of Approvals' notification port.
        self._notifications = notifications

    # --- reads (get_by_id/list inherited from BaseService) --------------
    def get_by_id_enriched(self, leave_request_id: uuid.UUID) -> LeaveRequestResponse:
        request = self.get_by_id(leave_request_id)  # raises LeaveRequestNotFoundError
        return self.to_enriched_response(request)

    def to_enriched_response(self, request: LeaveRequest) -> LeaveRequestResponse:
        leave_type = self._leave_types.get_by_id(request.leave_type_id)
        return leave_request_to_response(request, leave_type_name=leave_type.name if leave_type is not None else None)

    # --- Cross-module referential-integrity checks (round 15 items 3/4)
    # -----------------------------------------------------------------
    # Consumed through `LeaveService.has_active_request_covering_date`/
    # `has_any_active_request` by the reverse ports
    # `apps.attendance.application.ports.LeaveReferenceCheckPort` (Holiday)
    # and `apps.app_settings.application.ports.LeaveReferenceCheckPort`
    # (Default Week Off) — see those ports' docstrings for the full
    # rationale on why the dependency direction is reversed here.
    def has_active_request_covering_date(self, target_date: date) -> bool:
        return self._requests.exists_active_request_covering_date(target_date)

    def has_any_active_request(self) -> bool:
        return self._requests.exists_any_active_request()

    # --- writes -----------------------------------------------------
    def apply_leave(self, request: ApplyLeaveRequest) -> LeaveRequestResponse:
        """Full validation pipeline, in order: employee exists -> employee
        is eligible to apply (round 14 item 6) -> leave type exists/active
        -> date range is valid -> start date isn't in the past (unless
        configured to allow it) -> no exact duplicate -> no overlap with
        any other active request -> sufficient WORKING-DAY balance (round
        14 item 6 — not calendar days; see `working_days_calculator.py`).
        Each step raises its own specific exception on failure — see
        `LeaveValidationService`.
        """
        try:
            self._validate.validate_employee_exists(request.employee_id)
            self._validate.validate_employee_eligible_for_leave(request.employee_id)
            # Approval Engine (Phase 9) precondition — checked early,
            # before any date/balance work, since neither a no-manager nor
            # a manager-not-linked-to-Telegram employee can ever have this
            # leave request approved regardless of what the rest of the
            # pipeline finds.
            self._validate.validate_manager_available_for_approval(request.employee_id)
            leave_type = self._validate.validate_and_get_leave_type(request.leave_type_id)
            date_range = self._validate.build_date_range(request.start_date, request.end_date)
            self._validate.validate_not_past(request.start_date)
            self._validate.validate_no_duplicate(
                employee_id=request.employee_id, leave_type_id=request.leave_type_id, date_range=date_range
            )
            self._validate.validate_no_overlap(employee_id=request.employee_id, date_range=date_range)

            # Round 14 item 6 — working days exclude the configured
            # week-off day and any holiday within the requested range.
            # Resolved here (application layer), not in the domain
            # calculator itself, which stays framework/module-independent.
            week_off_weekday = self._settings.get_default_week_off_weekday()
            holiday_dates = self._holidays.get_holiday_dates_in_range(
                start_date=date_range.start_date, end_date=date_range.end_date
            )
            working_days = Decimal(
                calculate_working_days(
                    date_range, week_off_weekday=week_off_weekday, holiday_dates=holiday_dates
                )
            )

            self._validate.validate_sufficient_balance(
                employee_id=request.employee_id,
                leave_type_id=request.leave_type_id,
                year=date_range.start_date.year,
                requested_days=working_days,
            )
        except Exception:
            logger.warning(
                "Leave application rejected for employee=%s leave_type=%s (%s..%s)",
                request.employee_id,
                request.leave_type_id,
                request.start_date,
                request.end_date,
                exc_info=True,
            )
            raise

        # Round 14 item 2 — snapshot of available balance at the moment of
        # application, for the Leave Details page. Read-only (balance
        # itself is only ever mutated at approve/cancel-of-approved time —
        # see LeaveBalanceService), so this is safe to read outside the
        # write transaction below.
        balance_snapshot = self._balances.get_balance(
            employee_id=request.employee_id,
            leave_type_id=request.leave_type_id,
            year=date_range.start_date.year,
        ).available_days

        leave_request = LeaveRequest(
            id=generate_uuid7(),
            employee_id=request.employee_id,
            leave_type_id=request.leave_type_id,
            date_range=date_range,
            reason=request.reason,
            working_days=working_days,
            balance_at_application=balance_snapshot,
        )
        with self._uow:
            created = self._requests.create(leave_request)
            # Required side effect, not best-effort: runs inside the SAME
            # transaction as the LeaveRequest creation above, so a failure
            # to open an approval request (e.g. the generic engine finds no
            # chain resolver registered — a programming error, not a
            # runtime condition, since validate_manager_available_for_approval
            # already confirmed a manager exists and is Telegram-linked)
            # rolls the leave request back too. A leave request must never
            # exist without an open approval request behind it.
            self._approvals.create_approval_request(
                subject_id=created.id,
                requested_by_employee_id=created.employee_id,
                # Round 15 item 2 — every surface that renders this opaque
                # summary (the manager's Telegram approval request/pending
                # push, the HR web Decide dialog, any future notification
                # channel) must show both figures, not just calendar days.
                # This is the single place that composes the sentence; every
                # reader downstream (apps.approvals' notification adapter,
                # the Gateway's push formatters, DecideApprovalDialog.tsx)
                # only ever displays it verbatim.
                subject_summary=(
                    f"{leave_type.name}: {created.date_range.start_date} → "
                    f"{created.date_range.end_date} "
                    f"({created.total_days} day(s) total, {created.working_days} working day(s))"
                ),
            )
        self._event_bus.publish(
            LeaveRequestApplied(
                leave_request_id=created.id,
                employee_id=created.employee_id,
                leave_type_id=created.leave_type_id,
                start_date=created.date_range.start_date,
                end_date=created.date_range.end_date,
            )
        )
        logger.info(
            "Leave applied: request=%s employee=%s leave_type=%s %s..%s (%s day(s))",
            created.id,
            created.employee_id,
            created.leave_type_id,
            created.date_range.start_date,
            created.date_range.end_date,
            created.total_days,
        )
        return self.to_enriched_response(created)

    def cancel_leave(self, request: CancelLeaveRequest) -> LeaveRequestResponse:
        existing = self.get_by_id(request.leave_request_id)  # raises LeaveRequestNotFoundError

        if request.acting_employee_id is not None and existing.employee_id != request.acting_employee_id:
            raise LeaveRequestOwnershipError()

        was_approved = existing.status.value == "approved"
        try:
            cancelled = existing.cancel(
                cancelled_at=datetime.now(timezone.utc), reason=request.cancellation_reason
            )
        except Exception:
            logger.warning("Leave cancellation rejected for request=%s", request.leave_request_id, exc_info=True)
            raise

        with self._uow:
            saved = self._requests.update(cancelled)
            # Round 17 item 2 — a leave request must never leave a stale,
            # still-decidable approval request behind it once cancelled —
            # the mirror-image invariant of apply_leave's own "never without
            # one" (see that method's docstring). Runs inside the SAME
            # transaction as the leave request's own cancellation above, so
            # a failure here rolls both back together. No-op if there was
            # no PENDING approval request to close (e.g. this leave was
            # already fully approved/rejected before being cancelled) — see
            # `ApprovalRequestPort.cancel_approval_request`'s docstring.
            self._approvals.cancel_approval_request(subject_id=saved.id, reason=request.cancellation_reason)
        if was_approved:
            # Round 14 item 6 — balance is deducted/restored in WORKING
            # days, not calendar days (`total_days`).
            self._balances.decrease_used_days(
                employee_id=saved.employee_id,
                leave_type_id=saved.leave_type_id,
                year=saved.date_range.start_date.year,
                amount=saved.working_days,
            )
            # Round 14 items 6/8 — if this cancelled leave had already
            # started (and so had already flipped the employee's Current
            # Status), revert it immediately rather than waiting for
            # tomorrow's reconciliation job.
            self._sync_status_on_cancel(saved)
        # Round 15 item 6 / round 17 item 3 — notify the employee on EVERY
        # cancellation now, not just an already-approved one (previously
        # gated behind `if was_approved:`, so cancelling a still-PENDING
        # request silently notified no one). `_notify_leave_cancelled`
        # itself picks the right wording for each case. Best-effort (logged,
        # not raised): the cancellation itself is already fully committed
        # by this point.
        self._notify_leave_cancelled(saved, was_approved=was_approved)
        self._event_bus.publish(LeaveRequestCancelled(leave_request_id=saved.id, employee_id=saved.employee_id))
        logger.info("Leave cancelled: request=%s employee=%s", saved.id, saved.employee_id)
        return self.to_enriched_response(saved)

    # --- Approval module extension point ---------------------------
    # Built and unit-tested in Phase 8 as an integration point ahead of
    # the Approval Engine's arrival; now actually wired up (Phase 9) —
    # `apps.leave.interface.event_handlers.handle_approval_decided` calls
    # this in reaction to the generic engine's `ApprovalDecided` event.
    def approve(self, request: ApproveLeaveRequest) -> LeaveRequestResponse:
        existing = self.get_by_id(request.leave_request_id)
        approved = existing.approve(
            approved_by=request.approved_by, decided_at=datetime.now(timezone.utc), comments=request.comments
        )
        with self._uow:
            saved = self._requests.update(approved)
        # Round 14 item 6 — balance is deducted in WORKING days, not
        # calendar days (`total_days`).
        self._balances.increase_used_days(
            employee_id=saved.employee_id,
            leave_type_id=saved.leave_type_id,
            year=saved.date_range.start_date.year,
            amount=saved.working_days,
        )
        # Round 14 items 6/8 — if this leave's period already covers
        # today (approved for a start date that has already arrived, or
        # backdated), flip the employee's Current Status immediately
        # rather than waiting for tomorrow's reconciliation job.
        self._sync_status_on_approve(saved)
        self._event_bus.publish(
            LeaveRequestApproved(leave_request_id=saved.id, employee_id=saved.employee_id, approved_by=saved.approved_by)
        )
        logger.info("Leave approved: request=%s employee=%s by=%s", saved.id, saved.employee_id, saved.approved_by)
        return self.to_enriched_response(saved)

    def reject(self, request: RejectLeaveRequest) -> LeaveRequestResponse:
        existing = self.get_by_id(request.leave_request_id)
        rejected = existing.reject(decided_at=datetime.now(timezone.utc), comments=request.comments)
        with self._uow:
            saved = self._requests.update(rejected)
        self._event_bus.publish(LeaveRequestRejected(leave_request_id=saved.id, employee_id=saved.employee_id))
        logger.info("Leave rejected: request=%s employee=%s", saved.id, saved.employee_id)
        return self.to_enriched_response(saved)

    # --- Employee status integration (round 14 items 6/8) -----------
    def _sync_status_on_approve(self, saved: LeaveRequest) -> None:
        """Only acts when `saved.date_range.start_date <= today` — an
        approval for a future-dated leave is deliberately left to the
        daily reconciliation task (tasks.py's `apply_pending_leave_status_transitions`),
        so this employee isn't flipped into a leave status weeks before
        it actually starts. Swallows (logs, does not raise) any exception
        from the status port: a leave request is fully approved and its
        balance is fully deducted by this point regardless of whether the
        Employee Current Status side effect succeeds — the nightly job is
        the safety net for anything missed here (e.g. the employee was
        Terminated in between, which the entity itself blocks)."""
        leave_type = self._leave_types.get_by_id(saved.leave_type_id)
        if leave_type is None or leave_type.maps_to_employee_status is None:
            return
        if saved.date_range.start_date > date.today():
            return
        try:
            self._employee_status.enter_leave_status(saved.employee_id, leave_type.maps_to_employee_status)
        except Exception:
            logger.warning(
                "Could not sync employee=%s Current Status to %s for approved leave request=%s "
                "— will be retried by the daily reconciliation task.",
                saved.employee_id,
                leave_type.maps_to_employee_status,
                saved.id,
                exc_info=True,
            )

    def _sync_status_on_cancel(self, saved: LeaveRequest) -> None:
        """Mirror-image of `_sync_status_on_approve` — only acts when the
        cancelled leave's period had already started (so the employee's
        Current Status was actually flipped in the first place)."""
        leave_type = self._leave_types.get_by_id(saved.leave_type_id)
        if leave_type is None or leave_type.maps_to_employee_status is None:
            return
        if saved.date_range.start_date > date.today():
            return
        try:
            self._employee_status.exit_leave_status(saved.employee_id)
        except Exception:
            logger.warning(
                "Could not revert employee=%s Current Status after cancelling leave request=%s "
                "— will be retried by the daily reconciliation task.",
                saved.employee_id,
                saved.id,
                exc_info=True,
            )

    # --- Leave cancellation notification (round 15 item 6 / round 17 item 3) ---
    def _notify_leave_cancelled(self, saved: LeaveRequest, *, was_approved: bool) -> None:
        leave_type = self._leave_types.get_by_id(saved.leave_type_id)
        type_name = leave_type.name if leave_type is not None else "Leave"
        # Round 15 item 2 — shows both total calendar days and working
        # days, same composition convention as apply_leave's subject_summary.
        summary = (
            f"{type_name}: {saved.date_range.start_date} → {saved.date_range.end_date} "
            f"({saved.total_days} day(s) total, {saved.working_days} working day(s))"
        )
        try:
            self._notifications.notify_leave_cancelled(
                employee_id=saved.employee_id,
                leave_request_id=saved.id,
                summary=summary,
                was_approved=was_approved,
            )
        except Exception:
            logger.warning(
                "Could not send leave cancellation notification for employee=%s leave request=%s.",
                saved.employee_id,
                saved.id,
                exc_info=True,
            )
