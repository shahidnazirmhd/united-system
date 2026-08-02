"""Data migration: registers this module's permission codes in Identity's
permission table, and grants them to the default "Admin" role — same
discipline as apps/settings/migrations/0002_seed_settings_permissions.py.
"""
from __future__ import annotations

from django.db import migrations

ATTENDANCE_PERMISSIONS = [
    {"code": "attendance.view_attendance", "description": "View attendance data, including holidays."},
    {"code": "attendance.manage_holidays", "description": "Create and update holidays."},
]

ROLE_PERMISSION_GRANTS = {
    "Admin": ["attendance.view_attendance", "attendance.manage_holidays"],
}


def seed_attendance_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    RoleRecord = apps.get_model("identity", "RoleRecord")
    RolePermissionRecord = apps.get_model("identity", "RolePermissionRecord")

    permissions_by_code = {}
    for perm in ATTENDANCE_PERMISSIONS:
        record, _ = PermissionRecord.objects.get_or_create(
            code=perm["code"], defaults={"description": perm["description"], "module": "attendance"}
        )
        permissions_by_code[perm["code"]] = record

    for role_name, codes in ROLE_PERMISSION_GRANTS.items():
        try:
            role_record = RoleRecord.objects.get(name=role_name)
        except RoleRecord.DoesNotExist:
            continue
        for code in codes:
            RolePermissionRecord.objects.get_or_create(
                role=role_record, permission=permissions_by_code[code]
            )


def remove_attendance_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    PermissionRecord.objects.filter(code__in=[p["code"] for p in ATTENDANCE_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("attendance", "0001_initial"),
        ("identity", "0006_rename_admin_role_and_prune_system_roles"),
    ]

    operations = [
        migrations.RunPython(seed_attendance_permissions, remove_attendance_permissions),
    ]
