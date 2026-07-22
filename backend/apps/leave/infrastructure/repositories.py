"""Django ORM-backed implementations of the Leave repository interfaces.

Follows apps/employees/infrastructure/repositories.py's exact shape:
`DjangoLeaveBalanceRepository`/`DjangoLeaveRequestRepository` extend
shared_kernel's generic `DjangoBaseRepository` for CRUD/pagination, adding
only the entity-specific lookups a generic base can't express.
`DjangoLeaveTypeRepository` is hand-written (no generic base), matching
`DjangoDepartmentRepository`'s precedent for the same reason (see
domain/repositories.py's docstring).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.db.models import Q, Sum

from apps.leave.domain.entities import LeaveBalance, LeaveRequest, LeaveType
from apps.leave.domain.enums import ACTIVE_LEAVE_REQUEST_STATUSES, LeaveRequestStatus
from apps.leave.domain.repositories import LeaveBalanceRepository, LeaveRequestRepository, LeaveTypeRepository
from apps.leave.infrastructure.models import LeaveBalanceRecord, LeaveRequestRecord, LeaveTypeRecord
from shared_kernel.domain.value_objects import DateRange
from shared_kernel.infrastructure.base_repository import DjangoBaseRepository

_ACTIVE_STATUS_VALUES = [status.value for status in ACTIVE_LEAVE_REQUEST_STATUSES]


def _leave_type_to_domain(record: LeaveTypeRecord) -> LeaveType:
    return LeaveType(
        id=record.id,
        name=record.name,
        code=record.code,
        default_annual_days=record.default_annual_days,
        is_paid=record.is_paid,
        requires_approval=record.requires_approval,
        is_active=record.is_active,
    )


def _leave_balance_to_domain(record: LeaveBalanceRecord) -> LeaveBalance:
    return LeaveBalance(
        id=record.id,
        employee_id=record.employee_id,
        leave_type_id=record.leave_type_id,
        year=record.year,
        entitled_days=record.entitled_days,
        used_days=record.used_days,
        carried_forward_days=record.carried_forward_days,
    )


def _leave_request_to_domain(record: LeaveRequestRecord) -> LeaveRequest:
    return LeaveRequest(
        id=record.id,
        employee_id=record.employee_id,
        leave_type_id=record.leave_type_id,
        date_range=DateRange(start_date=record.start_date, end_date=record.end_date),
        reason=record.reason,
        status=LeaveRequestStatus(record.status),
        approved_by=record.approved_by,
        decided_at=record.decided_at,
        decision_comments=record.decision_comments,
        cancelled_at=record.cancelled_at,
        cancellation_reason=record.cancellation_reason,
    )


class DjangoLeaveTypeRepository(LeaveTypeRepository):
    def get_by_id(self, leave_type_id: uuid.UUID) -> LeaveType | None:
        record = LeaveTypeRecord.objects.filter(id=leave_type_id).first()
        return _leave_type_to_domain(record) if record is not None else None

    def get_by_code(self, code: str) -> LeaveType | None:
        record = LeaveTypeRecord.objects.filter(code=code).first()
        return _leave_type_to_domain(record) if record is not None else None

    def list_active(self) -> list[LeaveType]:
        return [_leave_type_to_domain(r) for r in LeaveTypeRecord.objects.filter(is_active=True).order_by("name")]

    def exists(self, leave_type_id: uuid.UUID) -> bool:
        return LeaveTypeRecord.objects.filter(id=leave_type_id, is_active=True).exists()


class DjangoLeaveBalanceRepository(DjangoBaseRepository[LeaveBalanceRecord, LeaveBalance], LeaveBalanceRepository):
    model = LeaveBalanceRecord

    def _to_entity(self, record: LeaveBalanceRecord) -> LeaveBalance:
        return _leave_balance_to_domain(record)

    def _to_record_kwargs(self, entity: LeaveBalance) -> dict[str, object]:
        return {
            "employee_id": entity.employee_id,
            "leave_type_id": entity.leave_type_id,
            "year": entity.year,
            "entitled_days": entity.entitled_days,
            "used_days": entity.used_days,
            "carried_forward_days": entity.carried_forward_days,
        }

    def get_by_employee_leave_type_year(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int
    ) -> LeaveBalance | None:
        record = self._base_queryset().filter(employee_id=employee_id, leave_type_id=leave_type_id, year=year).first()
        return self._to_entity(record) if record is not None else None

    def list_by_employee(self, *, employee_id: uuid.UUID, year: int) -> list[LeaveBalance]:
        records = self._base_queryset().filter(employee_id=employee_id, year=year).order_by("leave_type__name")
        return [self._to_entity(r) for r in records]


class DjangoLeaveRequestRepository(DjangoBaseRepository[LeaveRequestRecord, LeaveRequest], LeaveRequestRepository):
    model = LeaveRequestRecord

    def _to_entity(self, record: LeaveRequestRecord) -> LeaveRequest:
        return _leave_request_to_domain(record)

    def _to_record_kwargs(self, entity: LeaveRequest) -> dict[str, object]:
        return {
            "employee_id": entity.employee_id,
            "leave_type_id": entity.leave_type_id,
            "start_date": entity.date_range.start_date,
            "end_date": entity.date_range.end_date,
            "total_days": entity.total_days,
            "reason": entity.reason,
            "status": entity.status.value,
            "approved_by": entity.approved_by,
            "decided_at": entity.decided_at,
            "decision_comments": entity.decision_comments,
            "cancelled_at": entity.cancelled_at,
            "cancellation_reason": entity.cancellation_reason,
        }

    def get_overlapping_for_employee(
        self,
        *,
        employee_id: uuid.UUID,
        date_range: DateRange,
        exclude_request_id: uuid.UUID | None = None,
    ) -> list[LeaveRequest]:
        # Standard closed-interval overlap test: two ranges [a,b] and [c,d]
        # overlap iff a <= d and c <= b — matches
        # shared_kernel.domain.value_objects.DateRange.overlaps() exactly,
        # just expressed as a query instead of an in-memory comparison.
        queryset = self._base_queryset().filter(
            employee_id=employee_id,
            status__in=_ACTIVE_STATUS_VALUES,
            start_date__lte=date_range.end_date,
            end_date__gte=date_range.start_date,
        )
        if exclude_request_id is not None:
            queryset = queryset.exclude(id=exclude_request_id)
        return [self._to_entity(r) for r in queryset]

    def get_duplicate(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, date_range: DateRange
    ) -> LeaveRequest | None:
        record = self._base_queryset().filter(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            status__in=_ACTIVE_STATUS_VALUES,
            start_date=date_range.start_date,
            end_date=date_range.end_date,
        ).first()
        return self._to_entity(record) if record is not None else None

    def sum_pending_days(self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int) -> Decimal:
        # PENDING only — see domain/repositories.py's docstring for why
        # APPROVED is deliberately excluded (already counted in
        # LeaveBalance.used_days). A request's "year" is its start date's
        # calendar year — a request spanning a year boundary (e.g. Dec 30
        # -> Jan 2) counts entirely against the year it started in, the
        # same simplification `leave_balances.year` itself already makes by
        # being a single SMALLINT column rather than a per-day ledger.
        total = self._base_queryset().filter(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            status=LeaveRequestStatus.PENDING.value,
            start_date__year=year,
        ).aggregate(total=Sum("total_days"))["total"]
        return total if total is not None else Decimal("0")
