"""Data migration: seeds the five system roles named throughout
HRMS_Architecture.md and HRMS_Database_Design.md, plus a small starter set
of identity-scoped permissions.

Only identity-scoped permissions exist yet, because no other module exists
yet to define its own (leave.approve, payroll.run, etc.) — each future
module adds its own permission rows via its own migration, without ever
touching this one. That's the concrete demonstration of the Open/Closed
requirement this module was built to satisfy: PermissionRecord.code is just
a string column, open to any future module inserting new rows.

Reversible: the reverse migration removes exactly what forward created.
"""
from __future__ import annotations

from django.db import migrations

SYSTEM_ROLES = [
    {"name": "Employee", "description": "Baseline role held by every authenticated employee."},
    {"name": "Manager", "description": "Manages a team of direct reports."},
    {"name": "HR Admin", "description": "Administers user accounts, roles, and HR data."},
    {"name": "Payroll Admin", "description": "Administers payroll runs and compensation data."},
    {"name": "Recruiter", "description": "Manages job openings and candidates."},
]

IDENTITY_PERMISSIONS = [
    {"code": "identity.view_users", "description": "View user accounts."},
    {"code": "identity.manage_users", "description": "Create, deactivate, and update user accounts."},
    {"code": "identity.view_roles", "description": "View roles and their permissions."},
    {"code": "identity.manage_roles", "description": "Create roles and assign/revoke them from users."},
]

# Only HR Admin gets identity-administration permissions by default — the
# other four are business-facing roles with no reason to manage accounts.
ROLE_PERMISSION_GRANTS = {
    "HR Admin": [p["code"] for p in IDENTITY_PERMISSIONS],
}


def seed_roles_and_permissions(apps, schema_editor):
    RoleRecord = apps.get_model("identity", "RoleRecord")
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    RolePermissionRecord = apps.get_model("identity", "RolePermissionRecord")

    permissions_by_code = {}
    for perm in IDENTITY_PERMISSIONS:
        record, _ = PermissionRecord.objects.get_or_create(
            code=perm["code"], defaults={"description": perm["description"], "module": "identity"}
        )
        permissions_by_code[perm["code"]] = record

    for role in SYSTEM_ROLES:
        role_record, _ = RoleRecord.objects.get_or_create(
            name=role["name"],
            defaults={"description": role["description"], "is_system_role": True},
        )
        for code in ROLE_PERMISSION_GRANTS.get(role["name"], []):
            RolePermissionRecord.objects.get_or_create(
                role=role_record, permission=permissions_by_code[code]
            )


def remove_seeded_roles_and_permissions(apps, schema_editor):
    RoleRecord = apps.get_model("identity", "RoleRecord")
    PermissionRecord = apps.get_model("identity", "PermissionRecord")

    RoleRecord.objects.filter(name__in=[r["name"] for r in SYSTEM_ROLES], is_system_role=True).delete()
    PermissionRecord.objects.filter(code__in=[p["code"] for p in IDENTITY_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_roles_and_permissions, remove_seeded_roles_and_permissions),
    ]
