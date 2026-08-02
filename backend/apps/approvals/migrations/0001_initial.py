"""Initial migration for the generic Approval Engine module.

Hand-written, same discipline as apps/leave/migrations/0001_initial.py: no
network/database access in this sandbox to run `makemigrations` for real,
so every field here was cross-checked field-by-field against
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
    apps/leave/migrations/0001_initial.py's identical helper."""
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
            name="ApprovalRequestRecord",
            fields=[
                *_base_fields(),
                ("subject_type", models.CharField(max_length=100)),
                ("subject_id", models.UUIDField()),
                ("requested_by_employee_id", models.UUIDField()),
                ("subject_summary", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("current_level", models.PositiveSmallIntegerField(default=1)),
            ],
            options={"db_table": "approval_requests"},
        ),
        migrations.CreateModel(
            name="ApprovalStepRecord",
            fields=[
                *_base_fields(),
                ("level", models.PositiveSmallIntegerField()),
                ("approver_employee_id", models.UUIDField()),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("comments", models.TextField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approval_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="approvals.approvalrequestrecord",
                    ),
                ),
            ],
            options={"db_table": "approval_steps"},
        ),
        migrations.AddIndex(
            model_name="approvalrequestrecord",
            index=models.Index(fields=["subject_type", "subject_id"], name="approval_requests_subject_idx"),
        ),
        migrations.AddIndex(
            model_name="approvalrequestrecord",
            index=models.Index(fields=["requested_by_employee_id"], name="approval_req_requester_idx"),
        ),
        migrations.AddConstraint(
            model_name="approvalrequestrecord",
            constraint=models.CheckConstraint(
                check=models.Q(("current_level__gte", 1)), name="approval_requests_level_gte_1"
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalsteprecord",
            constraint=models.UniqueConstraint(
                fields=("approval_request", "level"), name="approval_steps_unique_request_level"
            ),
        ),
        migrations.AddIndex(
            model_name="approvalsteprecord",
            index=models.Index(fields=["approver_employee_id", "status"], name="approval_steps_appr_stat_idx"),
        ),
    ]
