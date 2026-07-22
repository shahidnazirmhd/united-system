"""Initial migration for the Leave module.

Hand-written, same discipline as apps/employees/migrations/0001_initial.py:
no PyPI/network/database access in this sandbox to run `makemigrations` for
real, so every field here was cross-checked field-by-field against
infrastructure/models.py. Run `python manage.py makemigrations --check`
after pulling this into an environment with dependencies installed, as a
final confirmation.
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models

import shared_kernel.infrastructure.uuid7


def _base_fields() -> list[tuple[str, object]]:
    """The five fields every BaseModel-derived model carries — see
    apps/employees/migrations/0001_initial.py's identical helper."""
    return [
        (
            "id",
            models.UUIDField(
                default=shared_kernel.infrastructure.uuid7.generate_uuid7,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("created_by", models.UUIDField(blank=True, null=True)),
        ("updated_by", models.UUIDField(blank=True, null=True)),
    ]


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LeaveTypeRecord",
            fields=[
                *_base_fields(),
                ("name", models.CharField(max_length=50, unique=True)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("default_annual_days", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("is_paid", models.BooleanField(default=True)),
                ("requires_approval", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"db_table": "leave_types"},
        ),
        migrations.CreateModel(
            name="LeaveBalanceRecord",
            fields=[
                *_base_fields(),
                ("employee_id", models.UUIDField()),
                ("year", models.SmallIntegerField()),
                ("entitled_days", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("used_days", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("carried_forward_days", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                (
                    "leave_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="balances",
                        to="leave.leavetyperecord",
                    ),
                ),
            ],
            options={"db_table": "leave_balances"},
        ),
        migrations.CreateModel(
            name="LeaveRequestRecord",
            fields=[
                *_base_fields(),
                ("employee_id", models.UUIDField()),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("total_days", models.DecimalField(decimal_places=2, max_digits=5)),
                ("reason", models.TextField(blank=True, null=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("approved_by", models.UUIDField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decision_comments", models.TextField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancellation_reason", models.TextField(blank=True, null=True)),
                (
                    "leave_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="requests",
                        to="leave.leavetyperecord",
                    ),
                ),
            ],
            options={"db_table": "leave_requests"},
        ),
        migrations.AddConstraint(
            model_name="leavebalancerecord",
            constraint=models.UniqueConstraint(
                fields=("employee_id", "leave_type", "year"), name="leave_balances_unique_emp_type_year"
            ),
        ),
        migrations.AddConstraint(
            model_name="leavebalancerecord",
            constraint=models.CheckConstraint(
                check=models.Q(("entitled_days__gte", 0)), name="leave_balances_entitled_gte_0"
            ),
        ),
        migrations.AddConstraint(
            model_name="leavebalancerecord",
            constraint=models.CheckConstraint(check=models.Q(("used_days__gte", 0)), name="leave_balances_used_gte_0"),
        ),
        migrations.AddConstraint(
            model_name="leavebalancerecord",
            constraint=models.CheckConstraint(
                check=models.Q(("carried_forward_days__gte", 0)), name="leave_balances_carried_forward_gte_0"
            ),
        ),
        migrations.AddIndex(
            model_name="leavebalancerecord",
            index=models.Index(fields=["employee_id"], name="leave_balances_employee_idx"),
        ),
        migrations.AddIndex(
            model_name="leaverequestrecord",
            index=models.Index(fields=["employee_id", "status"], name="leave_requests_emp_status_idx"),
        ),
        migrations.AddIndex(
            model_name="leaverequestrecord",
            index=models.Index(
                fields=["employee_id", "start_date", "end_date"], name="leave_requests_emp_dates_idx"
            ),
        ),
        migrations.AddConstraint(
            model_name="leaverequestrecord",
            constraint=models.CheckConstraint(
                check=models.Q(("end_date__gte", models.F("start_date"))), name="leave_requests_end_after_start"
            ),
        ),
        migrations.AddConstraint(
            model_name="leaverequestrecord",
            constraint=models.CheckConstraint(
                check=models.Q(("total_days__gt", 0)), name="leave_requests_total_days_positive"
            ),
        ),
    ]
