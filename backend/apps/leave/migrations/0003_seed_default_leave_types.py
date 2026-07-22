"""Data migration: seeds a small starter set of leave types.

`leave.leave_types` is a lookup table specifically so HR can add a new type
as a data change, not a deployment (HRMS_Database_Design.md section 2) —
this migration seeds a reasonable starting set, not an exhaustive or
permanent list; nothing prevents HR from adding more via a future "manage
leave types" endpoint once one exists.

Reversible: the reverse migration removes exactly the rows this one
created, matched by `code`.
"""
from __future__ import annotations

from django.db import migrations

DEFAULT_LEAVE_TYPES = [
    {
        "name": "Annual Leave",
        "code": "ANNUAL",
        "default_annual_days": "20.00",
        "is_paid": True,
        "requires_approval": True,
    },
    {
        "name": "Sick Leave",
        "code": "SICK",
        "default_annual_days": "10.00",
        "is_paid": True,
        "requires_approval": True,
    },
    {
        "name": "Unpaid Leave",
        "code": "UNPAID",
        "default_annual_days": "0.00",
        "is_paid": False,
        "requires_approval": True,
    },
]


def seed_default_leave_types(apps, schema_editor):
    LeaveTypeRecord = apps.get_model("leave", "LeaveTypeRecord")
    for leave_type in DEFAULT_LEAVE_TYPES:
        LeaveTypeRecord.objects.get_or_create(
            code=leave_type["code"],
            defaults={
                "name": leave_type["name"],
                "default_annual_days": leave_type["default_annual_days"],
                "is_paid": leave_type["is_paid"],
                "requires_approval": leave_type["requires_approval"],
                "is_active": True,
            },
        )


def remove_default_leave_types(apps, schema_editor):
    LeaveTypeRecord = apps.get_model("leave", "LeaveTypeRecord")
    LeaveTypeRecord.objects.filter(code__in=[lt["code"] for lt in DEFAULT_LEAVE_TYPES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("leave", "0002_seed_leave_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_default_leave_types, remove_default_leave_types),
    ]
