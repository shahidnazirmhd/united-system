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

from apps.leave.domain.enums import LeaveRequestStatus
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
        )

