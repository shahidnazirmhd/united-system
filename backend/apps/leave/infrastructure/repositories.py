"""Django ORM-backed implementations of the Leave repository interfaces.

Follows apps/employees/infrastructure/repositories.py's exact shape:
`DjangoLeaveBalanceRepository`/`DjangoLeaveRequestRepository`/(as of Phase
13) `DjangoLeaveTypeRepository` extend shared_kernel's generic
`DjangoBaseRepository` for CRUD/pagination, adding only the entity-specific
lookups a generic base can't express. `DjangoLeaveBalanceAdjustmentRepository`
is hand-written (no generic base) — see its own ABC's docstring
(domain/repositories.py) for why an audit trail deliberately never gets
`update`/`delete` at all, generic or otherwise.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth

from apps.leave.domain.entities import LeaveBalance, LeaveBalanceAdjustment, LeaveRequest, LeaveType
from apps.leave.domain.enums import ACTIVE_LEAVE_REQUEST_STATUSES, LeaveBalanceAdjustmentType, LeaveRequestStatus
from apps.leave.domain.repositories import (
    LeaveBalanceAdjustmentRepository,
    LeaveBalanceRepository,
    LeaveRequestRepository,
    LeaveStatisticsSnapshot,
    LeaveTypeRepository,
)
from apps.leave.infrastructure.models import (
    LeaveBalanceAdjustmentRecord,
    LeaveBalanceRecord,
    LeaveRequestRecord,
    LeaveTypeRecord,
)
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
        maps_to_employee_status=record.maps_to_employee_status,
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
        working_days=record.working_days,
        balance_at_application=record.balance_at_application,
        updated_at=record.updated_at,
        level1_skipped=record.level1_skipped,
        level1_skip_reason=record.level1_skip_reason,
        initiated_via=record.initiated_via,
        initiator_user_id=record.initiator_user_id,
        initiator_telegram_user_id=record.initiator_telegram_user_id,
    )


class DjangoLeaveTypeRepository(DjangoBaseRepository[LeaveTypeRecord, LeaveType], LeaveTypeRepository):
    """Phase 13 (Leave Type Management) — now built on the same generic
    `DjangoBaseRepository` `DjangoDepartmentRepository` was migrated onto in
    Phase 12, instead of the hand-written `get_by_id` this class started
    with. Base ordering `(DjangoBaseRepository[...], LeaveTypeRepository)`
    matches every other dual-inheriting repository in this codebase — see
    `DjangoBaseRepository`'s own docstring for why the order must agree
    everywhere."""

    model = LeaveTypeRecord

    def _to_entity(self, record: LeaveTypeRecord) -> LeaveType:
        return _leave_type_to_domain(record)

    def _to_record_kwargs(self, entity: LeaveType) -> dict[str, object]:
        return {
            "name": entity.name,
            "code": entity.code,
            "default_annual_days": entity.default_annual_days,
            "is_paid": entity.is_paid,
            "requires_approval": entity.requires_approval,
            "is_active": entity.is_active,
            "maps_to_employee_status": entity.maps_to_employee_status,
        }

    def get_by_code(self, code: str) -> LeaveType | None:
        record = LeaveTypeRecord.objects.filter(code=code).first()
        return _leave_type_to_domain(record) if record is not None else None

    def list_active(self) -> list[LeaveType]:
        return [_leave_type_to_domain(r) for r in LeaveTypeRecord.objects.filter(is_active=True).order_by("name")]

    def exists(self, leave_type_id: uuid.UUID) -> bool:
        # Stricter than DjangoBaseRepository's inherited generic exists() —
        # see LeaveTypeRepository.exists's docstring for why this override
        # is intentional, not a bug.
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
            "working_days": entity.working_days,
            "balance_at_application": entity.balance_at_application,
            "reason": entity.reason,
            "status": entity.status.value,
            "approved_by": entity.approved_by,
            "decided_at": entity.decided_at,
            "decision_comments": entity.decision_comments,
            "cancelled_at": entity.cancelled_at,
            "cancellation_reason": entity.cancellation_reason,
            "level1_skipped": entity.level1_skipped,
            "level1_skip_reason": entity.level1_skip_reason,
            "initiated_via": entity.initiated_via,
            "initiator_user_id": entity.initiator_user_id,
            "initiator_telegram_user_id": entity.initiator_telegram_user_id,
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

    # --- Employee status integration (round 14 items 6/8) -----------
    def list_approved_starting_on(self, target_date: date) -> list[LeaveRequest]:
        records = self._base_queryset().filter(
            status=LeaveRequestStatus.APPROVED.value, start_date=target_date
        )
        return [self._to_entity(r) for r in records]

    def list_employee_ids_with_approved_leave_covering(self, target_date: date) -> frozenset[uuid.UUID]:
        return frozenset(
            self.model.objects.filter(
                status=LeaveRequestStatus.APPROVED.value,
                start_date__lte=target_date,
                end_date__gte=target_date,
            ).values_list("employee_id", flat=True)
        )

    # --- Referential-integrity checks (round 15 items 3/4/5) -------------
    def exists_active_request_covering_date(self, target_date: date) -> bool:
        return self._base_queryset().filter(
            status__in=_ACTIVE_STATUS_VALUES,
            start_date__lte=target_date,
            end_date__gte=target_date,
        ).exists()

    def exists_any_active_request(self) -> bool:
        return self._base_queryset().filter(status__in=_ACTIVE_STATUS_VALUES).exists()

    def exists_active_request_for_leave_type(self, leave_type_id: uuid.UUID) -> bool:
        return self._base_queryset().filter(
            status__in=_ACTIVE_STATUS_VALUES,
            leave_type_id=leave_type_id,
        ).exists()

    def exists_active_or_upcoming_request_for_employee(self, employee_id: uuid.UUID, *, as_of: date) -> bool:
        # `end_date__gte=as_of` covers both "in progress right now" (started
        # on/before `as_of`, ends on/after it) and "entirely in the future"
        # (starts after `as_of`) in one comparison — a request that ended
        # before `as_of` is neither, and correctly excluded.
        return self._base_queryset().filter(
            employee_id=employee_id,
            status__in=_ACTIVE_STATUS_VALUES,
            end_date__gte=as_of,
        ).exists()

    def exists_active_or_upcoming_approved_request_for_employee(self, employee_id: uuid.UUID, *, as_of: date) -> bool:
        # Same date comparison as the PENDING/APPROVED version above,
        # narrowed to APPROVED only — see that abstract method's own
        # docstring (domain/repositories.py) for why PENDING must never
        # count here.
        return self._base_queryset().filter(
            employee_id=employee_id,
            status=LeaveRequestStatus.APPROVED.value,
            end_date__gte=as_of,
        ).exists()

    # --- Statistics (Phase 14: Dashboard) --------------------------------
    def get_statistics_snapshot(self, *, monthly_trend_since: date) -> LeaveStatisticsSnapshot:
        by_status = {
            row["status"]: row["count"]
            for row in self.model.objects.values("status").annotate(count=Count("id"))
        }
        by_leave_type = [
            (row["leave_type_id"], row["count"])
            for row in self.model.objects.values("leave_type_id").annotate(count=Count("id"))
        ]
        monthly = (
            self.model.objects.filter(created_at__date__gte=monthly_trend_since)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )
        monthly_trend = [(row["month"].strftime("%Y-%m"), row["count"]) for row in monthly]
        return LeaveStatisticsSnapshot(by_status=by_status, by_leave_type=by_leave_type, monthly_trend=monthly_trend)


def _leave_balance_adjustment_to_domain(record: LeaveBalanceAdjustmentRecord) -> LeaveBalanceAdjustment:
    return LeaveBalanceAdjustment(
        id=record.id,
        employee_id=record.employee_id,
        leave_type_id=record.leave_type_id,
        year=record.year,
        adjustment_type=LeaveBalanceAdjustmentType(record.adjustment_type),
        previous_entitled_days=record.previous_entitled_days,
        previous_used_days=record.previous_used_days,
        previous_carried_forward_days=record.previous_carried_forward_days,
        new_entitled_days=record.new_entitled_days,
        new_used_days=record.new_used_days,
        new_carried_forward_days=record.new_carried_forward_days,
        reason=record.reason,
    )


class DjangoLeaveBalanceAdjustmentRepository(LeaveBalanceAdjustmentRepository):
    """Hand-written, not `DjangoBaseRepository`-based — see the ABC's own
    docstring (domain/repositories.py) for why this audit trail must never
    expose `update`/`delete`, generic or otherwise."""

    def create(self, adjustment: LeaveBalanceAdjustment, *, created_by: uuid.UUID | None) -> LeaveBalanceAdjustment:
        record = LeaveBalanceAdjustmentRecord.objects.create(
            id=adjustment.id,
            employee_id=adjustment.employee_id,
            leave_type_id=adjustment.leave_type_id,
            year=adjustment.year,
            adjustment_type=adjustment.adjustment_type.value,
            previous_entitled_days=adjustment.previous_entitled_days,
            previous_used_days=adjustment.previous_used_days,
            previous_carried_forward_days=adjustment.previous_carried_forward_days,
            new_entitled_days=adjustment.new_entitled_days,
            new_used_days=adjustment.new_used_days,
            new_carried_forward_days=adjustment.new_carried_forward_days,
            reason=adjustment.reason,
            created_by=created_by,
        )
        return _leave_balance_adjustment_to_domain(record)

    def list_by_employee(
        self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID | None = None, year: int | None = None
    ) -> list[LeaveBalanceAdjustment]:
        queryset = LeaveBalanceAdjustmentRecord.objects.filter(employee_id=employee_id)
        if leave_type_id is not None:
            queryset = queryset.filter(leave_type_id=leave_type_id)
        if year is not None:
            queryset = queryset.filter(year=year)
        return [_leave_balance_adjustment_to_domain(r) for r in queryset.order_by("-created_at")]
