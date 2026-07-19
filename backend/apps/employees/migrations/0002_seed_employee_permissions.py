"""Data migration: registers this module's permission codes in Identity's
permission table, and grants them to sensible default roles.

This is the concrete proof of the Open/Closed promise
apps/identity/migrations/0002_seed_system_roles.py made: "each future
module adds its own permission rows via its own migration, without ever
touching this one." Nothing in apps/identity's migrations changes here —
this migration reaches into identity's tables using Django's historical
model API (`apps.get_model`), the standard, supported way to write a
cross-app data migration.

Depends on `identity.0002_seed_system_roles` so the HR Admin/Manager role
rows this migration grants permissions to are guaranteed to already exist
by the time it runs — not on identity's *code* (this file never imports
`apps.identity.infrastructure.models`), only on its migration state, which
is the correct, narrow coupling for a data migration to have.

Reversible: the reverse migration removes exactly what forward created.
"""
from __future__ import annotations

from django.db import migrations

EMPLOYEE_PERMISSIONS = [
    {"code": "employees.view_employees", "description": "View employee records."},
    {"code": "employees.manage_employees", "description": "Create, update, activate, and deactivate employee records."},
]

# HR Admin administers employee data directly; Manager needs read access to
# their reporting line. Neither grant is a hardcoded assumption baked into
# identity's own seed data (apps/identity/migrations/0002_seed_system_roles.py)
# — it's this module deciding, for itself, who gets its own permissions.
ROLE_PERMISSION_GRANTS = {
    "HR Admin": ["employees.view_employees", "employees.manage_employees"],
    "Manager": ["employees.view_employees"],
}


def seed_employee_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    RoleRecord = apps.get_model("identity", "RoleRecord")
    RolePermissionRecord = apps.get_model("identity", "RolePermissionRecord")

    permissions_by_code = {}
    for perm in EMPLOYEE_PERMISSIONS:
        record, _ = PermissionRecord.objects.get_or_create(
            code=perm["code"], defaults={"description": perm["description"], "module": "employees"}
        )
        permissions_by_code[perm["code"]] = record

    for role_name, codes in ROLE_PERMISSION_GRANTS.items():
        try:
            role_record = RoleRecord.objects.get(name=role_name)
        except RoleRecord.DoesNotExist:
            # Defensive only — identity's own seed migration guarantees
            # these roles exist by the time this migration's dependency is
            # satisfied; this branch protects against someone having
            # manually deleted a system role, not against a real ordering bug.
            continue
        for code in codes:
            RolePermissionRecord.objects.get_or_create(
                role=role_record, permission=permissions_by_code[code]
            )


def remove_employee_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    PermissionRecord.objects.filter(code__in=[p["code"] for p in EMPLOYEE_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0001_initial"),
        ("identity", "0002_seed_system_roles"),
    ]

    operations = [
        migrations.RunPython(seed_employee_permissions, remove_employee_permissions),
    ]
