"""Domain entities for Leave: LeaveType, LeaveBalance, LeaveRequest.

Plain Python, no Django — matching Employees'/Identity's precedent exactly
(see apps/employees/domain/entities.py's docstring). `LeaveRequest` is this
module's aggregate root; `LeaveType` and `LeaveBalance` are independent
entities of their own (unlike `Department`, neither is "only here so
LeaveRequest has an FK target" — both have their own repositories and, for
`LeaveType`, are directly requested read endpoints).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


from apps.leave.domain.enums import LeaveBalanceAdjustmentType, LeaveRequestStatus
from shared_kernel.domain.base_entity import Entity
from shared_kernel.domain.value_objects import DateRange


@dataclass(kw_only=True)
class LeaveType(Entity):
    name: str
    code: str
    default_annual_days: Decimal = Decimal("0")
    is_paid: bool = True
    requires_approval: bool = True
    is_active: bool = True
    # Round 14 items 6/8 — which Employee Current Status an approved
    # request of this type drives while it's in progress (see
    # domain/employee_status_mapping.py for the allowed values and the
    # reasoning for using plain strings, not an imported Employees enum).
    # `None` means this leave type never changes the employee's Current
    # Status at all (e.g. an unpaid leave type HR doesn't want reflected
    # there).
    maps_to_employee_status: str | None = None


@dataclass(kw_only=True)
class LeaveBalance(Entity):
    # Logical reference to employees.employees.id — plain UUID, never a
    # ForeignKey, per HRMS_Database_Design.md section 5 and matching this
    # exact field's own approved schema note ("logical, no FK").
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int
    entitled_days: Decimal = Decimal("0")
    used_days: Decimal = Decimal("0")
    carried_forward_days: Decimal = Decimal("0")

    @property
    def available_days(self) -> Decimal:
        return self.entitled_days + self.carried_forward_days - self.used_days

    def increase_used_days(self, amount: Decimal) -> "LeaveBalance":
        """Called only by `LeaveBalanceService` when a request transitions
        into `APPROVED` — never directly by `LeaveRequestService`, so all
        balance-mutation rules stay in one place (Single Responsibility)."""
        return self._with_used_days(self.used_days + amount)

    def decrease_used_days(self, amount: Decimal) -> "LeaveBalance":
        """Called when an `APPROVED` request is cancelled, to give the days
        back. Floors at zero rather than going negative — defensive only,
        this should be mathematically unreachable since a request can never
        be approved for more days than were available at approval time."""
        return self._with_used_days(max(Decimal("0"), self.used_days - amount))

    def _with_used_days(self, used_days: Decimal) -> "LeaveBalance":
        return LeaveBalance(
            id=self.id,
            employee_id=self.employee_id,
            leave_type_id=self.leave_type_id,
            year=self.year,
            entitled_days=self.entitled_days,
            used_days=used_days,
            carried_forward_days=self.carried_forward_days,
        )


@dataclass(kw_only=True)
class LeaveRequest(Entity):
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    date_range: DateRange
    reason: str | None = None
    status: LeaveRequestStatus = LeaveRequestStatus.PENDING
    # --- Approval extension point ---------------------------------------
    # Populated only by approve()/reject() below. Not written to by any
    # other code path this phase — see this module's architecture notes
    # ("Approval Preparation") for why these columns exist now.
    approved_by: uuid.UUID | None = None
    decided_at: datetime | None = None
    decision_comments: str | None = None
    # --- Cancellation ------------------------------------------------
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    # --- Working-day calculation (round 14 item 6) ------------------------
    # Computed once, at apply time, by `LeaveRequestService.apply_leave`
    # (via `domain/working_days_calculator.py`) and stored — not recomputed
    # on every read, matching `total_days`'s own "denormalized, stored"
    # precedent below exactly, and for the same practical reason: the
    # week-off/holiday configuration this value was computed against can
    # change later, but a request's own working_days must not silently
    # change retroactively with it. Balance deduction (approve/cancel) uses
    # this value, never `total_days`.
    working_days: Decimal = Decimal("0")
    # Snapshot of the employee's available balance for this leave type/year
    # at the moment they applied — round 14 item 2 ("display employee leave
    # balance at the time the leave was applied"). `None` only for legacy
    # rows created before this column existed.
    balance_at_application: Decimal | None = None
    # Phase 14 (Dashboard) — mirrors the ORM's own `auto_now` column
    # (BaseModel.updated_at). Bumped by EVERY lifecycle write to this row —
    # apply/approve/reject/cancel all call `LeaveRequestRepository.update()`
    # — which is exactly what makes ordering by this column (see
    # `LeaveService.list_all_requests_admin`, called with
    # `ordering=("-updated_at",)` by `apps.dashboard`'s recent-activity
    # adapter) a correct "what changed most recently, across every kind of
    # change" feed with no new query logic needed. `None` only for an
    # in-memory entity that was never persisted (e.g. inside a unit test
    # fake repository that doesn't set it).
    updated_at: datetime | None = None
    # --- HR Leave Workflow round (skip-level-1 + initiator tracking) -----
    # Set once, at apply time, by `LeaveRequestService.apply_leave` — never
    # changed afterwards by approve()/reject()/cancel() (they thread the
    # existing value through unchanged, same as `working_days`/
    # `balance_at_application` above). `level1_skipped` is only ever True
    # when `initiated_via == "hr"` AND the affected employee had no
    # notifiable manager (see `LeaveValidationService.evaluate_level1_approval`);
    # self-service (web or Telegram) applications always hard-require a
    # notifiable manager, so they can never produce a skip.
    level1_skipped: bool = False
    # One of `NoManagerAssignedError.code` / `ManagerNotLinkedToTelegramError.code`
    # (see domain/exceptions.py) when `level1_skipped` is True, else `None`.
    # Reusing the exception's own `code` string (not re-inventing a new
    # constant) keeps the "raise" path (self-service) and "evaluate" path
    # (HR preview + skip) permanently in sync.
    level1_skip_reason: str | None = None
    # Which channel actually submitted this request — `"hr"` (an HR/Admin
    # user applying on behalf of an employee via the web app),
    # `"telegram"` (the employee themself, via the Telegram bot), or `None`
    # (ordinary self-service web apply — the common case, no special
    # initiator display needed). Deliberately not a richer enum: these are
    # the only two channels the business ever asked to distinguish in the
    # UI (see requirement: "user name + employee ID and system request" /
    # "telegram user id + employee id and employee portal request").
    initiated_via: str | None = None
    # Populated only when `initiated_via == "hr"` — the `identity.users.id`
    # of the HR/Admin account that submitted this on the employee's behalf.
    # Plain UUID, never a ForeignKey, matching `LeaveBalance.employee_id`'s
    # own "logical reference, no FK" precedent.
    initiator_user_id: uuid.UUID | None = None
    # Populated only when `initiated_via == "telegram"` — the Telegram
    # user id of the employee who applied via the bot. `BigIntegerField`
    # at the ORM layer, matching `EmployeeRecord.telegram_user_id` exactly.
    initiator_telegram_user_id: int | None = None

    @property
    def total_days(self) -> Decimal:
        return Decimal(self.date_range.days)

    def cancel(self, *, cancelled_at: datetime, reason: str | None) -> "LeaveRequest":
        """PENDING/APPROVED -> CANCELLED. Rejects cancelling a request that
        is already `CANCELLED` or `REJECTED` (nothing to undo), or still
        `DRAFT` (not a real request yet — this phase never produces DRAFT,
        but the guard is here for when a future "save as draft" feature
        does, so cancel() doesn't need to change to accommodate it)."""
        from apps.leave.domain.exceptions import LeaveRequestNotCancellableError

        if self.status not in (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED):
            raise LeaveRequestNotCancellableError(
                f"Leave request {self.id} cannot be cancelled from status '{self.status.value}'."
            )
        return LeaveRequest(
            id=self.id,
            employee_id=self.employee_id,
            leave_type_id=self.leave_type_id,
            date_range=self.date_range,
            reason=self.reason,
            status=LeaveRequestStatus.CANCELLED,
            approved_by=self.approved_by,
            decided_at=self.decided_at,
            decision_comments=self.decision_comments,
            cancelled_at=cancelled_at,
            cancellation_reason=reason,
            working_days=self.working_days,
            balance_at_application=self.balance_at_application,
            level1_skipped=self.level1_skipped,
            level1_skip_reason=self.level1_skip_reason,
            initiated_via=self.initiated_via,
            initiator_user_id=self.initiator_user_id,
            initiator_telegram_user_id=self.initiator_telegram_user_id,
        )

    def approve(self, *, approved_by: uuid.UUID, decided_at: datetime, comments: str | None = None) -> "LeaveRequest":
        """Approval module extension point — PENDING -> APPROVED. Not
        called by any endpoint this phase; implemented and unit-tested so
        the future Approval module has a ready-made, already-correct
        integration point (see this phase's architecture notes)."""
        from apps.leave.domain.exceptions import LeaveRequestNotInPendingStateError

        if self.status != LeaveRequestStatus.PENDING:
            raise LeaveRequestNotInPendingStateError(
                f"Leave request {self.id} cannot be approved from status '{self.status.value}'."
            )
        return LeaveRequest(
            id=self.id,
            employee_id=self.employee_id,
            leave_type_id=self.leave_type_id,
            date_range=self.date_range,
            reason=self.reason,
            status=LeaveRequestStatus.APPROVED,
            approved_by=approved_by,
            decided_at=decided_at,
            decision_comments=comments,
            cancelled_at=self.cancelled_at,
            cancellation_reason=self.cancellation_reason,
            working_days=self.working_days,
            balance_at_application=self.balance_at_application,
            level1_skipped=self.level1_skipped,
            level1_skip_reason=self.level1_skip_reason,
            initiated_via=self.initiated_via,
            initiator_user_id=self.initiator_user_id,
            initiator_telegram_user_id=self.initiator_telegram_user_id,
        )

    def reject(self, *, decided_at: datetime, comments: str | None = None) -> "LeaveRequest":
        """Approval module extension point — PENDING -> REJECTED."""
        from apps.leave.domain.exceptions import LeaveRequestNotInPendingStateError

        if self.status != LeaveRequestStatus.PENDING:
            raise LeaveRequestNotInPendingStateError(
                f"Leave request {self.id} cannot be rejected from status '{self.status.value}'."
            )
        return LeaveRequest(
            id=self.id,
            employee_id=self.employee_id,
            leave_type_id=self.leave_type_id,
            date_range=self.date_range,
            reason=self.reason,
            status=LeaveRequestStatus.REJECTED,
            approved_by=self.approved_by,
            decided_at=decided_at,
            decision_comments=comments,
            cancelled_at=self.cancelled_at,
            cancellation_reason=self.cancellation_reason,
            working_days=self.working_days,
            balance_at_application=self.balance_at_application,
            level1_skipped=self.level1_skipped,
            level1_skip_reason=self.level1_skip_reason,
            initiated_via=self.initiated_via,
            initiator_user_id=self.initiator_user_id,
            initiator_telegram_user_id=self.initiator_telegram_user_id,
        )


@dataclass(kw_only=True)
class LeaveBalanceAdjustment(Entity):
    """Phase 13 (Leave Balance Adjustment / Opening) — one immutable audit
    row per `LeaveBalanceService.adjust_balance()` call. Unlike `LeaveBalance`
    above, this entity has no behavior/state-transition methods of its own:
    it is a write-once record of a fact that already happened, never itself
    mutated after creation (see `LeaveBalanceAdjustmentRepository`'s
    docstring — its ABC deliberately has no update/delete)."""

    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    year: int
    adjustment_type: LeaveBalanceAdjustmentType
    previous_entitled_days: Decimal
    previous_used_days: Decimal
    previous_carried_forward_days: Decimal
    new_entitled_days: Decimal
    new_used_days: Decimal
    new_carried_forward_days: Decimal
    reason: str

