"""Data migration: registers this module's permission codes in Identity's
permission table, and grants them to the default "Admin" role.

Same discipline as apps/approvals/migrations/0006_seed_level_approval_permissions.py
— reaches into identity's tables only via Django's historical model API,
never imports apps.identity's application code, and depends on
`identity.0006_rename_admin_role_and_prune_system_roles` (not just
`identity.0002`) so "Admin" is guaranteed to exist under that exact name —
see that migration's own docstring for why 0002 alone isn't enough.
"""
from __future__ import annotations

from django.db import migrations

SETTINGS_PERMISSIONS = [
    {"code": "settings.view_settings", "description": "View application settings."},
    {"code": "settings.manage_settings", "description": "Update application settings."},
]

ROLE_PERMISSION_GRANTS = {
    "Admin": ["settings.view_settings", "settings.manage_settings"],
}


def seed_settings_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    RoleRecord = apps.get_model("identity", "RoleRecord")
    RolePermissionRecord = apps.get_model("identity", "RolePermissionRecord")

    permissions_by_code = {}
    for perm in SETTINGS_PERMISSIONS:
        record, _ = PermissionRecord.objects.get_or_create(
            code=perm["code"], defaults={"description": perm["description"], "module": "settings"}
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


def remove_settings_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    PermissionRecord.objects.filter(code__in=[p["code"] for p in SETTINGS_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app_settings", "0001_initial"),
        ("identity", "0006_rename_admin_role_and_prune_system_roles"),
    ]

    operations = [
        migrations.RunPython(seed_settings_permissions, remove_settings_permissions),
    ]
