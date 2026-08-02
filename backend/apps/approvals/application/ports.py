"""Outbound ports for the Approval Engine's application layer.

Three distinct ports, each pointed at a different kind of dependency:

* `ApprovalChainResolverPort` — implemented and registered BY each subject
  module (Leave today), never by this module itself. This is the
  mechanism that lets the engine support dynamic/future approval levels
  without ever being modified: `ApprovalService` asks whichever resolver is
  registered for a given `subject_type` "who approves level N of this
  request?" and gets back either an `ApproverAssignment` (a specific
  employee, or "anyone holding this permission code" — see
  `domain/value_objects.py`) or `None` (chain complete). See
  `application/registry.py`'s `chain_resolver_registry` for how a resolver
  instance gets attached to a `subject_type` string, and
  `apps.leave.infrastructure.leave_approval_chain_resolver` for the first
  concrete implementation.

* `ApprovalAuthorizationPort` — how this engine checks "does employee X
  currently hold permission code Y?" for a permission-based step's
  `decide()` call and for aggregating a caller's permission-based pending
  steps into "My Pending Approvals." Only ever consulted for permission-
  based steps; a single-employee step's authorization check never calls
  this. The concrete implementation
  (infrastructure/authorization_adapter.py) is the only file in this module
  allowed to import `apps.identity` — same Dependency Inversion as
  `EmployeeLookupPort` below, just pointed at Identity's roles/permissions
  instead of Employees' profile data.

* `ApprovalNotificationPort` — how this engine notifies an approver a
  decision is needed, and notifies a requester once one is made. Deliberately
  generic (a caller-supplied `subject_summary` string, never any
  subject-specific formatting) — the concrete implementation
  (infrastructure/telegram_notification_adapter.py) dispatches a Celery task
  that calls the Telegram Gateway's own internal notify endpoint, but this
  port's contract says nothing about Telegram; a future email/SMS/web-push
  notification channel would satisfy the same contract.

* `EmployeeLookupPort` — exactly the same Dependency Inversion pattern
  `apps.leave.application.ports.EmployeeLookupPort` already established:
  this module needs to resolve "which employee is the JWT/Telegram caller"
  without ever importing `apps.employees`'s internals. Kept as this
  module's own copy rather than importing Leave's (or Employees') —
  interface-adjacent ports are per-module by convention throughout this
  codebase, avoiding a needless cross-module dependency for a small,
  stable shape. Also exposes `get_telegram_chat_id`, which Leave's own
  port does not need but this module does (see
  infrastructure/telegram_notification_adapter.py — Telegram's Bot API
  addresses a chat by `chat_id`, distinct from `telegram_user_id`; see
  apps.employees.domain.entities.Employee's docstring for why both are
  stored).
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from apps.approvals.domain.value_objects import ApproverAssignment


class ApprovalChainResolverPort(ABC):
    @abstractmethod
    def resolve_next_approver(
        self,
        *,
        subject_type: str,
        subject_id: uuid.UUID,
        requested_by_employee_id: uuid.UUID,
        level: int,
    ) -> ApproverAssignment | None:
        """Returns who must approve `level` of this request — either a
        specific employee or a permission code any qualifying employee may
        act on (`ApproverAssignment.for_employee`/`.for_permission`) — or
        `None` if there is no further level, i.e. the chain is complete once
        the *previous* level's decision was an approval. Called with
        `level=1` exactly once, at `ApprovalService.create_approval_request`
        time; called again with `level=N+1` each time level `N` is
        approved, until this returns `None` (or a rejection occurs at some
        level, which ends the chain without ever calling this again).

        A `None` result at `level=1` means "this subject cannot be
        submitted for approval at all" — `ApprovalService` raises
        `NoApproverAvailableError` in that case; the subject module is
        expected to have already prevented this upstream with its own
        validation (see `apps.leave.domain.exceptions.NoManagerAssignedError`),
        so this should be unreachable in practice, not a normal user-facing
        outcome.
        """
        raise NotImplementedError


class ApprovalNotificationPort(ABC):
    @abstractmethod
    def notify_approval_requested(
        self,
        *,
        approver_employee_id: uuid.UUID,
        subject_summary: str,
        approval_request_id: uuid.UUID,
        level: int,
    ) -> None:
        """A new approval request (or a newly-advanced level) needs this
        employee's decision."""
        raise NotImplementedError

    @abstractmethod
    def notify_decision_made(
        self,
        *,
        requested_by_employee_id: uuid.UUID,
        subject_summary: str,
        final_status: str,
        comments: str | None,
        approval_request_id: uuid.UUID,
    ) -> None:
        """The request this employee originally submitted has reached a
        final decision (approved or rejected)."""
        raise NotImplementedError

    @abstractmethod
    def notify_step_advanced(
        self,
        *,
        requested_by_employee_id: uuid.UUID,
        subject_summary: str,
        message: str,
        new_level: int,
        approval_request_id: uuid.UUID,
    ) -> None:
        """The request this employee originally submitted was just approved
        at a NON-final level and has moved on to a further level — distinct
        from `notify_decision_made`, which only ever fires once the whole
        chain concludes. `message` is the opaque, subject-supplied sentence
        from `ApproverAssignment.requester_notification_message` (Leave
        review round) — this port never composes wording of its own, same
        as every other method here treating `subject_summary` as opaque."""
        raise NotImplementedError


class EmployeeLookupPort(ABC):
    @abstractmethod
    def get_employee_id_by_user_id(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """Resolves the employee record linked to an Identity User account
        — used by the JWT-authenticated self-service endpoints to turn
        `request.user.user_id` into the employee id this module's service
        methods operate on, mirroring
        `apps.leave.application.ports.EmployeeLookupPort` exactly."""
        raise NotImplementedError

    @abstractmethod
    def get_employee_id_by_telegram_user_id(self, telegram_user_id: int) -> uuid.UUID | None:
        """Resolves the employee linked to a Telegram account — used by the
        Gateway-facing `.../telegram/*` endpoints."""
        raise NotImplementedError

    @abstractmethod
    def get_telegram_chat_id(self, employee_id: uuid.UUID) -> int | None:
        """The employee's Telegram chat id, if linked — `None` if the
        employee doesn't exist or isn't linked to Telegram. Used only by
        `infrastructure/telegram_notification_adapter.py`'s Celery task to
        address the Gateway's `POST /internal/notify` call; never used by
        `ApprovalService` itself, which only ever handles employee ids, not
        Telegram identifiers."""
        raise NotImplementedError

    @abstractmethod
    def get_employee_display_info(self, employee_id: uuid.UUID) -> tuple[str, str] | None:
        """`(full_name, employee_code)` for `employee_id`, or `None` if the
        employee no longer exists. Mirrors
        `apps.leave.application.ports.EmployeeLookupPort
        .get_employee_display_info` exactly (kept as this module's own copy
        for the same "no cross-module port sharing" reason every other port
        method here already follows). Used by `ApprovalService` to enrich a
        `for_employee` step's response with a display name/code (Approval
        Workflow Changes review round) — never for a permission-based step,
        which has no single employee to name."""
        raise NotImplementedError


class ApprovalAuthorizationPort(ABC):
    @abstractmethod
    def get_permission_codes_for_employee(self, employee_id: uuid.UUID) -> frozenset[str]:
        """Every permission code granted to `employee_id`, via whatever
        Identity roles their linked user account holds — an empty
        `frozenset` if the employee has no linked user account (or doesn't
        exist; this port never raises for that, since "not authorized" and
        "unknown" collapse to the same outcome here: no permissions).

        Used by `ApprovalService.decide` (to check a permission-based
        step's authorization) and `list_pending_for_approver` (to also
        surface permission-based steps the caller currently qualifies for)
        — never by a single-employee step's authorization check, which
        never needs to know anything about permissions at all."""
        raise NotImplementedError
