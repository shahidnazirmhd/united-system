"""Data migration: backfills `maps_to_employee_status` on the two seeded
leave types ("ANNUAL"/"SICK", see `0003_seed_default_leave_types.py`) that
should have always driven Employee Current Status but never actually had
this column set.

**Why this migration exists (real bug found in production use):** the
`maps_to_employee_status` column was added in `0005_working_days_and_status_mapping.py`
without a backfill, and the frontend's Leave Type Management UI never
exposed a control for setting it at all (a genuine gap, fixed alongside
this migration — see `frontend/src/modules/leave/components/LeaveTypeFormDialog.tsx`).
The practical effect: every real leave type, including the two seeded
defaults, had `maps_to_employee_status = NULL` in every environment, so
`LeaveRequestService._sync_status_on_approve`/`_sync_status_on_cancel` and
the daily reconciliation task (`apps.leave.infrastructure.tasks`) were
silent no-ops — an employee's Current Status never actually flipped to
Sick Leave/Annual Leave on approval, despite that entire mechanism being
otherwise correctly wired end-to-end (event handler, Celery Beat schedule,
domain entity methods). This migration fixes existing data; the frontend
fix (same round) is what stops it from recurring for any future/renamed
leave type.

Matched by `code` (`"ANNUAL"`/`"SICK"`), same idempotent `get_or_create`-
adjacent style as the seed migration itself — a no-op if HR already
changed these via the (now fixed) UI, or if these rows don't exist at all
(e.g. a fresh environment that never ran the demo seed). Reversible: sets
the column back to `NULL` for exactly these two codes.
"""
from __future__ import annotations

from django.db import migrations

_MAPPING = {
    "ANNUAL": "annual_leave",
    "SICK": "sick_leave",
}


def backfill_status_mapping(apps, schema_editor):
    LeaveTypeRecord = apps.get_model("leave", "LeaveTypeRecord")
    for code, status in _MAPPING.items():
        LeaveTypeRecord.objects.filter(code=code, maps_to_employee_status__isnull=True).update(
            maps_to_employee_status=status
        )


def unset_status_mapping(apps, schema_editor):
    LeaveTypeRecord = apps.get_model("leave", "LeaveTypeRecord")
    LeaveTypeRecord.objects.filter(code__in=_MAPPING.keys()).update(maps_to_employee_status=None)


class Migration(migrations.Migration):
    dependencies = [
        ("leave", "0006_hr_workflow_skip_and_initiator"),
    ]

    operations = [
        migrations.RunPython(backfill_status_mapping, unset_status_mapping),
    ]
