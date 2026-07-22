"""Data migration: registers this module's permission codes in Identity's
permission table, and grants them to sensible default roles.

Same discipline as apps/employees/migrations/0002_seed_employee_permissions.py
— reaches into identity's tables only via Django's historical model API,
never imports apps.identity's application code, and depends on
`identity.0002_seed_system_roles` so the role rows it grants to are
guaranteed to exist first.
"""
from __future__ import annotations

from django.db import migrations

LEAVE_PERMISSIONS = [
    {"code": "leave.view_leave", "description": "View leave types, balances, and requests."},
    {"code": "leave.manage_leave", "description": "Apply for, cancel, and (once built) approve/reject leave requests."},
]

# HR Admin administers leave data directly; Manager needs read access to
# their reporting line's leave (e.g. for planning coverage), matching
# Employees' identical HR Admin/Manager split.
ROLE_PERMISSION_GRANTS = {
    "HR Admin": ["leave.view_leave", "leave.manage_leave"],
    "Manager": ["leave.view_leave"],
}


def seed_leave_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    RoleRecord = apps.get_model("identity", "RoleRecord")
    RolePermissionRecord = apps.get_model("identity", "RolePermissionRecord")

    permissions_by_code = {}
    for perm in LEAVE_PERMISSIONS:
        record, _ = PermissionRecord.objects.get_or_create(
            code=perm["code"], defaults={"description": perm["description"], "module": "leave"}
        )
        permissions_by_code[perm["code"]] = record

    for role_name, codes in ROLE_PERMISSION_GRANTS.items():
        try:
            role_record = RoleRecord.objects.get(name=role_name)
        except RoleRecord.DoesNotExist:
            # Defensive only — identity's own seed migration guarantees
            # these roles exist by the time this migration's dependency is
            # satisfied.
            continue
        for code in codes:
            RolePermissionRecord.objects.get_or_create(
                role=role_record, permission=permissions_by_code[code]
            )


def remove_leave_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    PermissionRecord.objects.filter(code__in=[p["code"] for p in LEAVE_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("leave", "0001_initial"),
        ("identity", "0002_seed_system_roles"),
    ]

    operations = [
        migrations.RunPython(seed_leave_permissions, remove_leave_permissions),
    ]
