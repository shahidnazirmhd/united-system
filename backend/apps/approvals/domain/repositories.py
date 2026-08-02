"""Repository interfaces for the generic Approval Engine.

Both `ApprovalRequestRepository` and `ApprovalStepRepository` extend
`BaseRepository` (shared_kernel.domain.repository) — both have real CRUD
needs of their own, matching `apps.leave.domain.repositories`'s
`LeaveBalanceRepository`/`LeaveRequestRepository` precedent exactly.
"""
from __future__ import annotations

import uuid
from abc import abstractmethod

from apps.approvals.domain.entities import ApprovalRequest, ApprovalStep
from shared_kernel.domain.repository import BaseRepository


class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    @abstractmethod
    def get_pending_by_subject(self, *, subject_type: str, subject_id: uuid.UUID) -> ApprovalRequest | None:
        """The currently-open (status=PENDING) approval request for this
        subject, if any — a subject is expected to have at most one open
        approval request at a time (enforced by the calling module's own
        pre-conditions, e.g. Leave only ever calls `create_approval_request`
        once per newly-created `LeaveRequest`), so this returns a single
        entity rather than a list."""
        raise NotImplementedError

    @abstractmethod
    def list_by_subject(self, *, subject_type: str, subject_id: uuid.UUID) -> list[ApprovalRequest]:
        """Every approval request (any status) ever raised for this
        subject — for audit/history reads."""
        raise NotImplementedError


class ApprovalStepRepository(BaseRepository[ApprovalStep]):
    @abstractmethod
    def get_by_request_and_level(self, *, approval_request_id: uuid.UUID, level: int) -> ApprovalStep | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_request(self, *, approval_request_id: uuid.UUID) -> list[ApprovalStep]:
        """Every step (every level reached so far) for one approval
        request, ordered by level — the full decision trail (Approval
        History)."""
        raise NotImplementedError

    @abstractmethod
    def list_pending_for_approver(
        self, *, approver_employee_id: uuid.UUID, held_permission_codes: frozenset[str]
    ) -> list[ApprovalStep]:
        """Every currently-PENDING step this employee can act on, across
        every approval request and every subject type — either assigned to
        them specifically, or assigned by a permission code in
        `held_permission_codes`. What "My Pending Approvals" (self-service
        REST and Telegram's /pending_approvals) both read from."""
        raise NotImplementedError
