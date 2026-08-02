"""Adds `restricted_to_channel` to `ApprovalStepRecord` — Approval Workflow
Changes review round: which channel (`ApprovalChannel.WEB`/`.TELEGRAM`) a
step may be decided from, or `NULL` for "either, no restriction" (the only
behavior that existed before this migration). See
`apps.approvals.domain.value_objects.ApproverAssignment
.restricted_to_channel`'s docstring for the full reasoning — this engine
itself has no opinion on which level of which subject module should be
restricted; only `apps.leave.infrastructure.leave_approval_chain_resolver`
sets a non-null value, for its own two levels.

Hand-written, same discipline as every other migration in this codebase:
no database access in this sandbox to run `makemigrations` for real, so
every operation here was cross-checked field-by-field against
infrastructure/models.py. Run `python manage.py makemigrations --check`
after pulling this into an environment with dependencies installed, as a
final confirmation.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("approvals", "0003_permission_based_approver"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalsteprecord",
            name="restricted_to_channel",
            field=models.CharField(
                blank=True,
                choices=[("web", "Web"), ("telegram", "Telegram")],
                max_length=20,
                null=True,
            ),
        ),
    ]
