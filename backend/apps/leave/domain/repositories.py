"""Repository interfaces for Leave.

`LeaveTypeRepository` deliberately does NOT extend `BaseRepository` — no
"manage leave types" endpoint was requested this phase (only "Get Leave
Types"), so it gets the same minimal, read-oriented ABC shape
`apps.employees.domain.repositories.DepartmentRepository` uses for the same
reason. `LeaveBalanceRepository` and `LeaveRequestRepository` DO extend
`BaseRepository` — both have real create/read/update needs of their own
this phase.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from decimal import Decimal

from apps.leave.domain.entities import LeaveBalance, LeaveRequest, LeaveType
from shared_kernel.domain.repository import BaseRepository
from shared_kernel.domain.value_objects import DateRange


class LeaveTypeRepository(ABC):
    @abstractmethod
    def get_by_id(self, leave_type_id: uuid.UUID) -> LeaveType | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_code(self, code: str) -> LeaveType | None:
        raise NotImplementedError

    @abstractmethod
    def list_active(self) -> list[LeaveType]:
        raise NotImplementedError

    @abstractmethod
    def exists(self, leave_type_id: uuid.UUID) -> bool:
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
