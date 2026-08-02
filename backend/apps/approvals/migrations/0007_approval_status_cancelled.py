"""Adds `"cancelled"` to `ApprovalRequestRecord.status`/`ApprovalStepRecord
.status`'s `choices=` — round 17 item 2: the subject module (e.g. Leave) can
now close a still-open approval request when the subject itself is
cancelled, distinct from an approver's own rejection (see
`apps.approvals.domain.enums.ApprovalStatus`/`ApprovalStepStatus`'s new
`CANCELLED` member docstrings, and `ApprovalService.cancel_for_subject`).

`choices=` is Django-side validation metadata only — neither field has a DB
CHECK constraint tying it to the enum's members (see
infrastructure/models.py), so this migration is a no-op at the database
level, recorded purely so `makemigrations --check` stays clean against the
model's new `choices=` value.

Hand-written, same discipline as every other migration in this codebase: no
database access in this sandbox to run `makemigrations` for real, so this
was cross-checked field-by-field against infrastructure/models.py. Run
`python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("approvals", "0006_seed_level_approval_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="approvalrequestrecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="approvalsteprecord",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
