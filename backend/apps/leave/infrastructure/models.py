"""Django ORM models for Leave.

Named with a "Record" suffix, matching Identity's and Employees' convention
exactly. Table names are exactly the names HRMS_Database_Design.md already
approved for the `leave` schema (`leave_types`, `leave_balances`) — no
further module prefixing needed since those names already read
unambiguously on their own, unlike `employees_employees`/`employees_departments`
which needed the `employees_` prefix to avoid a bare `departments` table
name colliding across modules in a real deployment. `leave_requests`
follows the same already-approved naming, extended to the (not-yet-scoped
in the design doc) third table this module designs itself.
"""
from __future__ import annotations

from django.db import models

from apps.leave.domain.enums import LeaveRequestStatus
from shared_kernel.infrastructure.base_models import BaseModel


class LeaveTypeRecord(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, unique=True)
    default_annual_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_paid = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "leave_types"

    def __str__(self) -> str:
        return self.name


class LeaveBalanceRecord(BaseModel):
    # Logical reference to employees_employees.id — plain UUID, never a
    # ForeignKey, per HRMS_Database_Design.md section 5 and this exact
    # column's own approved schema note ("logical, no FK").
    employee_id = models.UUIDField()
    leave_type = models.ForeignKey(LeaveTypeRecord, on_delete=models.RESTRICT, related_name="balances")
    year = models.SmallIntegerField()
    entitled_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    used_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    carried_forward_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = "leave_balances"
        constraints = [
            models.UniqueConstraint(
                fields=["employee_id", "leave_type", "year"], name="leave_balances_unique_emp_type_year"
            ),
            models.CheckConstraint(check=models.Q(entitled_days__gte=0), name="leave_balances_entitled_gte_0"),
            models.CheckConstraint(check=models.Q(used_days__gte=0), name="leave_balances_used_gte_0"),
            models.CheckConstraint(
                check=models.Q(carried_forward_days__gte=0), name="leave_balances_carried_forward_gte_0"
            ),
        ]
        indexes = [
            models.Index(fields=["employee_id"], name="leave_balances_employee_idx"),
        ]

    def __str__(self) -> str:
        return f"balance employee:{self.employee_id} type:{self.leave_type_id} year:{self.year}"


class LeaveRequestRecord(BaseModel):
    # Logical reference to employees_employees.id — same reasoning as
    # LeaveBalanceRecord.employee_id above.
    employee_id = models.UUIDField()
    leave_type = models.ForeignKey(LeaveTypeRecord, on_delete=models.RESTRICT, related_name="requests")
    start_date = models.DateField()
    end_date = models.DateField()
    # Denormalized, stored (not recomputed on every read) — see
    # domain/entities.py LeaveRequest.total_days's docstring for why this is
    # persisted rather than purely derived: it's cheap to aggregate for
    # reporting and it's what balance restoration reads on cancel, without
    # needing to re-derive it from start/end every time.
    total_days = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=LeaveRequestStatus.choices(), default=LeaveRequestStatus.PENDING.value
    )
    # --- Approval extension point (see domain/entities.py) ---------------
    # Logical reference to identity_users.id — plain UUID, never a
    # ForeignKey (cross-module).
    approved_by = models.UUIDField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_comments = models.TextField(null=True, blank=True)
    # --- Cancellation ------------------------------------------------
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "leave_requests"
        indexes = [
            # The exact shape get_overlapping_for_employee/list_by_employee
            # query by — see infrastructure/repositories.py.
            models.Index(fields=["employee_id", "status"], name="leave_requests_emp_status_idx"),
            models.Index(fields=["employee_id", "start_date", "end_date"], name="leave_requests_emp_dates_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(end_date__gte=models.F("start_date")), name="leave_requests_end_after_start"),
            models.CheckConstraint(check=models.Q(total_days__gt=0), name="leave_requests_total_days_positive"),
        ]

    def __str__(self) -> str:
        return f"leave-request employee:{self.employee_id} {self.start_date}..{self.end_date} ({self.status})"
