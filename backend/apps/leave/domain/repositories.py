"""Repository interfaces for Leave.

`LeaveTypeRepository` extends `BaseRepository` as of Phase 13 (Leave Type
Management) — the same transition `apps.employees.domain.repositories
.DepartmentRepository` went through in Phase 12, for the identical reason:
it started read-only (only "Get Leave Types" was in scope), and now that
Create/Edit are real requirements, it gains the generic create/update/list/
get_by_id/delete contract instead of hand-rolling its own. `exists()` below
is still overridden with domain-specific ("active only") filtering — see
its docstring — which is a legitimate per-module override of the generic
contract, not a divergence from it. `LeaveBalanceRepository` and
`LeaveRequestRepository` already extended `BaseRepository` from this
module's first phase.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from apps.leave.domain.entities import LeaveBalance, LeaveBalanceAdjustment, LeaveRequest, LeaveType
from shared_kernel.domain.repository import BaseRepository
from shared_kernel.domain.value_objects import DateRange


class LeaveTypeRepository(BaseRepository[LeaveType]):
    @abstractmethod
    def get_by_code(self, code: str) -> LeaveType | None:
        raise NotImplementedError

    @abstractmethod
    def list_active(self) -> list[LeaveType]:
        raise NotImplementedError

    @abstractmethod
    def exists(self, leave_type_id: uuid.UUID) -> bool:
        """Deliberately stricter than `BaseRepository.exists`'s generic
        contract: `True` only for an *active* leave type. Existing callers
        (`LeaveValidationService`'s apply-leave pipeline) rely on this to
        mean "usable for a new leave request," not merely "a row exists" —
        `get_by_id` (inherited, unfiltered) is what Phase 13's admin
        create/update flow uses instead when it genuinely needs to see an
        inactive row (e.g. to reactivate it)."""
        raise NotImplementedError


class LeaveBalanceRepository(BaseRepository[LeaveBalance]):
    @abstractmethod
    def get_by_employee_leave_type_year(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int
    ) -> LeaveBalance | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_employee(self, *, employee_id: uuid.UUID, year: int) -> list[LeaveBalance]:
        raise NotImplementedError


class LeaveRequestRepository(BaseRepository[LeaveRequest]):
    @abstractmethod
    def get_overlapping_for_employee(
        self,
        *,
        employee_id: uuid.UUID,
        date_range: DateRange,
        exclude_request_id: uuid.UUID | None = None,
    ) -> list[LeaveRequest]:
        """Every currently-active (PENDING/APPROVED — see
        `domain.enums.ACTIVE_LEAVE_REQUEST_STATUSES`) request for this
        employee, across every leave type, whose dates overlap
        `date_range`. `exclude_request_id` lets a future "edit dates" or
        the approve/reject extension point re-run this check against the
        request's own row without it trivially overlapping itself."""
        raise NotImplementedError

    @abstractmethod
    def get_duplicate(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, date_range: DateRange
    ) -> LeaveRequest | None:
        """An exact-match active request for the same employee, leave type,
        and date range — a stricter special case of overlap, reported with
        its own, clearer exception (see
        `domain.exceptions.DuplicateLeaveRequestError`)."""
        raise NotImplementedError

    @abstractmethod
    def sum_pending_days(self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int) -> Decimal:
        """Total `total_days` across every still-`PENDING` request for this
        employee/leave type/year — the "already reserved, not yet
        approved" amount the sufficient-balance check subtracts from
        `LeaveBalance.available_days` (see
        `application/services/leave_validation_service.py`).

        Deliberately excludes `APPROVED` requests: an approved request's
        days are already reflected in `LeaveBalance.used_days` (moved there
        by `LeaveRequestService.approve()`), so summing both here would
        double-count the same days against the same balance.
        """
        raise NotImplementedError

    # --- Employee status integration (round 14 items 6/8) -----------
    @abstractmethod
    def list_approved_starting_on(self, target_date: date) -> list[LeaveRequest]:
        """Every `APPROVED` request whose `start_date` is exactly
        `target_date` — the daily reconciliation task's "START" pass
        (`apps.leave.infrastructure.tasks.reconcile_leave_employee_statuses`),
        catching approvals made for a future-dated leave that
        `LeaveRequestService._sync_status_on_approve` deliberately left
        untouched at approval time."""
        raise NotImplementedError

    @abstractmethod
    def list_employee_ids_with_approved_leave_covering(self, target_date: date) -> frozenset[uuid.UUID]:
        """Every employee id with at least one `APPROVED` request whose
        date range covers `target_date` — the daily reconciliation task's
        "END" pass uses this to tell which currently-on-leave-status
        employees should now revert (no approved leave covers today for
        them anymore, whether because it ended or was cancelled)."""
        raise NotImplementedError

    # --- Referential-integrity checks for other modules' mutations
    # (round 15 items 3/4/5) -------------------------------------------
    # These three back the reverse ports described in
    # apps.attendance.application.ports.LeaveReferenceCheckPort and
    # apps.app_settings.application.ports.LeaveReferenceCheckPort (Holiday
    # and Default Week Off both depend on Leave to answer "would mutating
    # me invalidate a real leave request"), plus LeaveTypeService's own
    # same-module use of the third. "Active" is deliberately PENDING or
    # APPROVED (ACTIVE_LEAVE_REQUEST_STATUSES) in all three — a
    # draft/rejected/cancelled request was never actually relied upon, so
    # it is not a reason to block someone else's edit.
    @abstractmethod
    def exists_active_request_covering_date(self, target_date: date) -> bool:
        """True if any PENDING/APPROVED request's date range includes
        `target_date` — used to block deactivating/editing a Holiday that
        falls inside a real leave request's span (that request's frozen
        `working_days` was computed assuming this date is a holiday)."""
        raise NotImplementedError

    @abstractmethod
    def exists_any_active_request(self) -> bool:
        """True if any PENDING/APPROVED request exists at all, system-wide
        — used to block changing the Default Week Off setting, since every
        active request's frozen `working_days` was computed against the
        week-off weekday in effect when it was applied for."""
        raise NotImplementedError

    @abstractmethod
    def exists_active_request_for_leave_type(self, leave_type_id: uuid.UUID) -> bool:
        """True if any PENDING/APPROVED request references this leave
        type — used to block editing/deactivating a LeaveType that a real
        leave request still depends on."""
        raise NotImplementedError


class LeaveBalanceAdjustmentRepository(ABC):
    """Deliberately NOT `BaseRepository` — this is an append-only audit
    trail (see `infrastructure/models.py`'s `LeaveBalanceAdjustmentRecord`
    docstring); exposing `update`/`delete` on the interface at all would
    make "corrupt the audit trail" a reachable call, not just an unused
    one. Only `create` and the one read (`list_by_employee`) a future
    balance-history view needs are declared."""

    @abstractmethod
    def create(self, adjustment: LeaveBalanceAdjustment, *, created_by: uuid.UUID | None) -> LeaveBalanceAdjustment:
        """`created_by` is who performed the adjustment — kept as an
        explicit parameter rather than a field on `LeaveBalanceAdjustment`
        itself, since "who/when" is a persistence-layer audit concern
        (`BaseModel.created_by`/`created_at`), not part of the domain
        entity's own data (matching how every other `*Record`'s
        `created_by` is set by the repository, never carried on the
        domain entity — see e.g. `DjangoEmployeeRepository`)."""
        raise NotImplementedError

    @abstractmethod
    def list_by_employee(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID | None = None, year: int | None = None
    ) -> list[LeaveBalanceAdjustment]:
        raise NotImplementedError
