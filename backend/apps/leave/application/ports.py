"""Outbound ports for the Leave application layer.

`EmployeeLookupPort` is how this module learns anything about an employee
without ever importing `apps.employees`'s domain/application layers, or
touching its database tables — the same Dependency Inversion already used
for `EmployeeOTPEmailPort` (apps/employees/application/ports.py), just
pointed at another module's public service instead of an external system
(SMTP). The concrete adapter (infrastructure/employee_lookup_adapter.py)
is the only file in this module allowed to import `apps.employees` at all,
and it imports that module's already-composed public `EmployeeService`
(via its own `interface/dependencies.py`), never its infrastructure
repositories directly — calling into another module's *public application
API* is the correct cross-module boundary in a modular monolith, not a
violation of "always keep modules independent."
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import date


class EmployeeLookupPort(ABC):
    @abstractmethod
    def employee_exists(self, employee_id: uuid.UUID) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_employee_id_by_user_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """Resolves the employee record linked to an Identity User account
        — used by the JWT-authenticated self-service endpoints (`.../me/`)
        to turn `request.user.user_id` into the employee id every Leave
        service method actually operates on."""
        raise NotImplementedError

    @abstractmethod
    def get_employee_id_by_telegram_user_id(self, telegram_user_id: int) -> uuid.UUID | None:
        """Resolves the employee linked to a Telegram account — used by the
        Gateway-facing `.../telegram/*` endpoints, mirroring
        `apps.employees.interface.telegram_views.EmployeeTelegramProfileView`'s
        resolution exactly."""
        raise NotImplementedError

    # --- Approval Engine (Phase 9) ---------------------------------------
    @abstractmethod
    def get_manager_employee_id(self, employee_id: uuid.UUID) -> uuid.UUID | None:
        """The employee id of `employee_id`'s manager, or `None` if none is
        assigned — `apps.employees.application.dtos.EmployeeResponse`
        already carries `manager_id` on every read, so this needs no new
        capability on the Employees side, only a new method on this port.
        Used by `LeaveValidationService.validate_manager_available_for_approval`
        and by `apps.leave.infrastructure.leave_approval_chain_resolver
        .LeaveApprovalChainResolver` (level 1's approver)."""
        raise NotImplementedError

    @abstractmethod
    def get_employee_display_info(self, employee_id: uuid.UUID) -> tuple[str, str] | None:
        """`(full_name, employee_code)` for `employee_id`, or `None` if the
        employee no longer exists. Used only by the HR-wide "manage" leave
        request list (Phase 13 review requirement) to show which employee
        each row belongs to — every other read already has employee context
        from the caller (self-service: the caller *is* the employee;
        single-employee history: the caller already picked one), so no
        other call site needs this."""
        raise NotImplementedError

    @abstractmethod
    def is_employee_linked_to_telegram(self, employee_id: uuid.UUID) -> bool:
        """Whether `employee_id` (typically a manager, not the applicant)
        currently has a linked Telegram account —
        `EmployeeResponse.is_linked_to_telegram` already exists for exactly
        this. Used by the same validation method above, to enforce the
        Phase 9 brief's second precondition: a manager with no linked
        Telegram account cannot be notified or act on a decision, so the
        leave request must not be submitted at all."""
        raise NotImplementedError

    # --- Leave eligibility / status integration (round 14 items 6/8) -----
    @abstractmethod
    def is_employee_eligible_for_leave(self, employee_id: uuid.UUID) -> bool:
        """Whether `employee_id`'s Current Status permits applying for
        leave right now (round 14 item 6) — backed by
        `apps.employees.domain.entities.Employee.is_eligible_for_leave` on
        the other side of this port. Used by
        `LeaveValidationService.validate_employee_eligible_for_leave`."""
        raise NotImplementedError

    @abstractmethod
    def list_employee_ids_on_leave_status(self) -> list[uuid.UUID]:
        """Every employee id currently on a system-managed leave status
        (SICK_LEAVE/ANNUAL_LEAVE) — the daily reconciliation task's "END"
        pass batch-checks each of these against
        `LeaveRequestRepository.list_employee_ids_with_approved_leave_covering`
        to decide who should revert."""
        raise NotImplementedError

    # --- Leave cancellation notification (round 15 item 6) ---------------
    @abstractmethod
    def get_telegram_chat_id(self, employee_id: uuid.UUID) -> int | None:
        """The employee's linked Telegram chat id, or `None` if they have
        none — mirrors `apps.approvals.application.ports.EmployeeLookupPort
        .get_telegram_chat_id` exactly (same underlying
        `EmployeeResponse.telegram_chat_id` field), duplicated onto this
        module's own port rather than imported from Approvals, matching
        this whole port's existing precedent of never depending on a peer
        module's port definitions, only on `apps.employees`' public
        service. Used by `CeleryLeaveNotificationAdapter` to resolve who to
        push the cancellation notice to."""
        raise NotImplementedError


class EmployeeStatusPort(ABC):
    """How Leave *writes* to an employee's Current Status (round 14 items
    6/8) — the mirror-image direction of `EmployeeLookupPort` above (a
    read-only port): Dependency Inversion still points at Employees'
    public application service, just for a mutating call this time. A
    separate ABC from `EmployeeLookupPort` rather than two more abstract
    methods bolted onto it, matching Interface Segregation — a caller that
    only ever reads (e.g. `LeaveValidationService`) is never handed
    something that can mutate Employees' data.
    """

    @abstractmethod
    def enter_leave_status(self, employee_id: uuid.UUID, leave_status: str) -> None:
        """Called when an approved leave's period starts (immediately at
        approval time if it already started, or by the daily
        reconciliation job otherwise). Lets
        `InvalidCurrentStatusTransitionError` (e.g. employee is
        Terminated/Resigned — see
        `apps.employees.domain.entities.Employee.enter_leave_status`'s own
        guard) surface as-is rather than swallowing it here, so the caller
        (a Celery task processing many employees) can decide whether to
        log-and-continue."""
        raise NotImplementedError

    @abstractmethod
    def exit_leave_status(self, employee_id: uuid.UUID) -> None:
        """Called when an approved leave's period ends (immediately at
        cancel time if it already started, or by the daily reconciliation
        job otherwise)."""
        raise NotImplementedError


class SettingsLookupPort(ABC):
    """How Leave depends on the generic Settings module (round 14 item 4)
    — Dependency Inversion pointed at `apps.settings`'s public application
    service, same pattern as `EmployeeLookupPort` pointed at
    `apps.employees`'s."""

    @abstractmethod
    def get_default_week_off_weekday(self) -> int:
        """0=Monday ... 6=Sunday (`date.weekday()` convention) — see
        `apps.settings`'s `default_week_off` seed migration for the stored
        convention this reads."""
        raise NotImplementedError


class HolidayLookupPort(ABC):
    """How Leave depends on the generic Attendance module's Holiday
    Management (round 14 item 5) — Dependency Inversion pointed at
    `apps.attendance`'s public application service, same pattern as
    `EmployeeLookupPort` pointed at `apps.employees`'s."""

    @abstractmethod
    def get_holiday_dates_in_range(self, *, start_date: date, end_date: date) -> frozenset[date]:
        raise NotImplementedError


class ApprovalRequestPort(ABC):
    """How Leave depends on the generic Approval Engine (`apps.approvals`)
    — Dependency Inversion pointed at another module's public application
    service, exactly like `EmployeeLookupPort` above is pointed at
    Employees'. The concrete adapter
    (`infrastructure/approval_request_adapter.py`) is the only file in this
    module allowed to import `apps.approvals`, and even then only its
    public composition root
    (`apps.approvals.interface.dependencies.build_approval_service`),
    never that module's infrastructure directly — same discipline as
    `EmployeeServiceLookupAdapter`.

    Unlike `EmployeeLookupPort` (Leave depending on a peer HR module for a
    *read*), this is Leave depending on a foundational, generic engine for
    a *required write side effect*: `LeaveRequestService.apply_leave` calls
    this inside the same `UnitOfWork`/transaction it uses to create the
    `LeaveRequest` itself, so a failure to create the approval request
    rolls back the leave request too (see that method's docstring) — a
    leave request that requires approval must never exist without an open
    approval request behind it.
    """

    @abstractmethod
    def create_approval_request(
        self,
        *,
        subject_id: uuid.UUID,
        requested_by_employee_id: uuid.UUID,
        subject_summary: str,
        start_at_level: int = 1,
    ) -> None:
        """Opens a new approval request for the leave request identified by
        `subject_id` (`LeaveRequest.id`). `subject_type` is fixed to
        `"leave.leave_request"` by the adapter itself — callers in this
        module never need to know or repeat that string.

        `start_at_level` (HR Leave Workflow round, item 1) — defaults to 1
        (unchanged behavior for every existing caller). `LeaveRequestService
        .apply_leave` passes `2` only when
        `LeaveValidationService.evaluate_level1_approval` determined the
        HR-on-behalf applicant's employee has no notifiable manager,
        skipping straight to HR/Admin (level 2) review. This module decides
        the level; the adapter and the underlying engine only execute it —
        see `apps.approvals.application.dtos.CreateApprovalRequestRequest
        .start_at_level`'s own docstring for the engine side of this."""
        raise NotImplementedError

    @abstractmethod
    def cancel_approval_request(self, *, subject_id: uuid.UUID, reason: str | None = None) -> None:
        """Round 17 item 2 — closes the currently-open approval request for
        the leave request identified by `subject_id`, if one exists. A
        no-op if none is open (e.g. this leave request was already fully
        approved/rejected before being cancelled) — see
        `apps.approvals.application.services.approval_service.ApprovalService
        .cancel_for_subject`'s docstring for the full idempotency reasoning.
        `subject_type` is fixed by the adapter, exactly like
        `create_approval_request` above. Called by
        `LeaveRequestService.cancel_leave` inside the SAME
        `UnitOfWork`/transaction it uses to persist the leave request's own
        cancellation — a cancelled leave request must never leave a stale,
        still-decidable approval request behind it, the same "never without
        one" invariant `apply_leave` already enforces in reverse (see that
        method's docstring)."""
        raise NotImplementedError


class LeaveNotificationPort(ABC):
    """How Leave pushes a Telegram notification directly to an employee
    (round 15 item 6: notify on cancellation of an already-approved leave
    request) — deliberately Leave's OWN channel, not a reuse of
    `apps.approvals.application.ports.ApprovalNotificationPort`. That port's
    concrete Celery task/payload shape is Approval-Engine-specific (a
    mandatory `approval_request_id`, and three fixed `notification_type`
    values, none of which is "an approval-independent decision Leave made
    on its own") — a leave cancellation is not an approval-engine decision
    at all (there is no open approval request to attach it to by the time
    it fires), so bending that port to fit would mean faking an
    `approval_request_id` that doesn't exist. This port instead mirrors
    that one's *shape* (a thin, fire-and-forget push) without borrowing its
    coupling — its own adapter, its own Celery task, and its own new
    `notification_type` branch on the SAME generic Gateway `/internal/notify`
    endpoint (which was already built to be extended this way — see that
    endpoint's own code comments).
    """

    @abstractmethod
    def notify_leave_cancelled(
        self, *, employee_id: uuid.UUID, leave_request_id: uuid.UUID, summary: str, was_approved: bool
    ) -> None:
        """Fire-and-forget: the caller (`LeaveRequestService.cancel_leave`)
        wraps this in a try/except and only logs a failure — a leave
        request is fully cancelled (and, if it was approved, its balance
        fully restored) by the time this is called regardless of whether
        the notification itself succeeds, the same "required domain effect
        vs. best-effort side channel" split every other notification call
        in this codebase already makes (see e.g.
        `LeaveRequestService._sync_status_on_cancel`'s own docstring).

        Round 17 item 3 — called on EVERY cancellation now, not just an
        already-approved one; `was_approved` lets the adapter/Gateway pick
        the right wording for each case ("your approved leave has been
        cancelled" vs "your pending leave request has been cancelled and
        its approval was closed") — see
        `apps.leave.infrastructure.tasks.send_leave_cancelled_notification`
        and `telegram_gateway/src/formatting/leave_formatter
        .format_leave_cancelled_push`."""
        raise NotImplementedError
