"""Round 14 item 6/8 schema changes:

- `LeaveTypeRecord.maps_to_employee_status` — which Employee Current Status
  an approved request of this type drives (see
  domain/employee_status_mapping.py).
- `LeaveRequestRecord.working_days` — the value balance is actually
  deducted against, replacing `total_days` for that purpose (see
  domain/entities.py LeaveRequest.working_days's docstring).
- `LeaveRequestRecord.balance_at_application` — snapshot for the Leave
  Details page (round 14 item 2).

Backfills `working_days = total_days` for every pre-existing row as a
best-effort default — this codebase has no record of what week-off/holiday
configuration was in effect when each historical request was applied, so
"assume every calendar day was a working day" is the least-wrong
approximation available; `balance_at_application` is left `NULL` for these
rows (see that column's own "None only for legacy rows" docstring).

Hand-written, same discipline as every other migration in this project.
Run `python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation.
"""
from __future__ import annotations

from django.db import migrations, models


def backfill_working_days(apps, schema_editor):
    LeaveRequestRecord = apps.get_model("leave", "LeaveRequestRecord")
    LeaveRequestRecord.objects.update(working_days=models.F("total_days"))


def noop_reverse(apps, schema_editor):
    # Nothing to undo — reverting this migration drops the columns
    # entirely (see RemoveField below, run automatically on `migrate
    # leave 0004`), which already discards this data.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("leave", "0004_leave_balance_adjustment"),
    ]

    operations = [
        migrations.AddField(
            model_name="leavetyperecord",
            name="maps_to_employee_status",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="leaverequestrecord",
            name="working_days",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name="leaverequestrecord",
            name="balance_at_application",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.RunPython(backfill_working_days, noop_reverse),
    ]
