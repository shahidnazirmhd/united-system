"""Phase 13 (Leave Balance Adjustment / Opening) — adds the
`leave_balance_adjustments` immutable audit table. Hand-written, same
discipline as 0001_initial.py: no database access in this sandbox to run
`makemigrations` for real, so every field here was cross-checked
field-by-field against infrastructure/models.py. Run
`python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation.
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models

import shared_kernel.infrastructure.uuid7


class Migration(migrations.Migration):
    dependencies = [
        ("leave", "0003_seed_default_leave_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeaveBalanceAdjustmentRecord",
            fields=[
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
                ("employee_id", models.UUIDField()),
                ("year", models.SmallIntegerField()),
                (
                    "adjustment_type",
                    models.CharField(choices=[("opening", "Opening"), ("adjustment", "Adjustment")], max_length=20),
                ),
                ("previous_entitled_days", models.DecimalField(decimal_places=2, max_digits=5)),
                ("previous_used_days", models.DecimalField(decimal_places=2, max_digits=5)),
                ("previous_carried_forward_days", models.DecimalField(decimal_places=2, max_digits=5)),
                ("new_entitled_days", models.DecimalField(decimal_places=2, max_digits=5)),
                ("new_used_days", models.DecimalField(decimal_places=2, max_digits=5)),
                ("new_carried_forward_days", models.DecimalField(decimal_places=2, max_digits=5)),
                ("reason", models.TextField()),
                (
                    "leave_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="balance_adjustments",
                        to="leave.leavetyperecord",
                    ),
                ),
            ],
            options={"db_table": "leave_balance_adjustments"},
        ),
        migrations.AddIndex(
            model_name="leavebalanceadjustmentrecord",
            index=models.Index(
                fields=["employee_id", "leave_type", "year"], name="leave_bal_adj_emp_yr_idx"
            ),
        ),
    ]
