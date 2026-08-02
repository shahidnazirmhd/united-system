"""Approval Workflow Changes v2 — relaxes `ApprovalStepRecord`'s
approver-mode constraint from "exactly one of `approver_employee_id`/
`approver_permission_code`" to "at least one," and adds two new columns:

* `permission_required_for_channel` — only meaningful when BOTH approver
  fields are set (a new "dual-mode" step): names the one channel on which
  `approver_permission_code` governs instead of `approver_employee_id`. See
  `apps.approvals.domain.value_objects.ApproverAssignment
  .for_employee_or_permission_by_channel`'s docstring — this is what lets
  Leave's level 1 stay decidable by the manager via Telegram (identity),
  while the web HR system is instead gated by holding
  `approvals.level1_approve` (permission), whether or not the web caller is
  literally the manager.
* `decided_by_employee_id` — who actually clicked Approve/Reject, distinct
  from `approver_employee_id` (who was originally assigned/referenced).
  Lets a permission-based or dual-mode step correctly show "approved/
  rejected by <the real decider's name>" even when that isn't whoever was
  statically referenced on the row.

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
        ("approvals", "0004_approval_step_restricted_channel"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="approvalsteprecord",
            name="approval_steps_exactly_one_approver_mode",
        ),
        migrations.AddConstraint(
            model_name="approvalsteprecord",
            constraint=models.CheckConstraint(
                check=~models.Q(("approver_employee_id__isnull", True), ("approver_permission_code__isnull", True)),
                name="approval_steps_at_least_one_approver_mode",
            ),
        ),
        migrations.AddField(
            model_name="approvalsteprecord",
            name="permission_required_for_channel",
            field=models.CharField(
                blank=True,
                choices=[("web", "Web"), ("telegram", "Telegram")],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="approvalsteprecord",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(("permission_required_for_channel__isnull", True))
                    | (
                        models.Q(("approver_employee_id__isnull", False))
                        & models.Q(("approver_permission_code__isnull", False))
                    )
                ),
                name="approval_steps_channel_permission_requires_dual_mode",
            ),
        ),
        migrations.AddField(
            model_name="approvalsteprecord",
            name="decided_by_employee_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
