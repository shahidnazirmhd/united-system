"""Adds permission-based approver assignment to `ApprovalStepRecord`:
`approver_employee_id` becomes nullable, `approver_permission_code` is new,
and a CheckConstraint enforces exactly one of the two is ever set — see
`apps.approvals.domain.value_objects.ApproverAssignment`'s docstring for
why (a level like Leave's HR/Admin stage can now be assigned to "anyone
holding this permission code" instead of one named employee).

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
        ("approvals", "0002_seed_approval_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="approvalsteprecord",
            name="approver_employee_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="approvalsteprecord",
            name="approver_permission_code",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddConstraint(
            model_name="approvalsteprecord",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(("approver_employee_id__isnull", False), ("approver_permission_code__isnull", True))
                    | models.Q(("approver_employee_id__isnull", True), ("approver_permission_code__isnull", False))
                ),
                name="approval_steps_exactly_one_approver_mode",
            ),
        ),
        migrations.AddIndex(
            model_name="approvalsteprecord",
            index=models.Index(
                fields=["approver_permission_code", "status"], name="approval_steps_perm_stat_idx"
            ),
        ),
    ]
