"""Data migration: registers this module's permission codes in Identity's
permission table, and grants them to sensible default roles.

Same discipline as apps/leave/migrations/0002_seed_leave_permissions.py —
reaches into identity's tables only via Django's historical model API,
never imports apps.identity's application code, and depends on
`identity.0002_seed_system_roles` so the role rows it grants to are
guaranteed to exist first.
"""
from __future__ import annotations

from django.db import migrations

APPROVAL_PERMISSIONS = [
    {"code": "approvals.view_approvals", "description": "View approval requests, steps, and history."},
    {"code": "approvals.decide_approvals", "description": "Approve or reject an approval request assigned to you."},
]

# Every employee who might ever be someone's manager needs to be able to
# decide approvals assigned to them — granted broadly to HR Admin and
# Manager, matching apps.leave's identical HR Admin/Manager split. Deciding
# itself is additionally guarded per-request by ApprovalService (only the
# specific employee named as the current step's approver may act on it,
# checked in application code, never by role alone) — this permission only
# gates "can this principal reach the decide endpoint at all."
ROLE_PERMISSION_GRANTS = {
    "HR Admin": ["approvals.view_approvals", "approvals.decide_approvals"],
    "Manager": ["approvals.view_approvals", "approvals.decide_approvals"],
}


def seed_approval_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    RoleRecord = apps.get_model("identity", "RoleRecord")
    RolePermissionRecord = apps.get_model("identity", "RolePermissionRecord")

    permissions_by_code = {}
    for perm in APPROVAL_PERMISSIONS:
        record, _ = PermissionRecord.objects.get_or_create(
            code=perm["code"], defaults={"description": perm["description"], "module": "approvals"}
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


def remove_approval_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    PermissionRecord.objects.filter(code__in=[p["code"] for p in APPROVAL_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("approvals", "0001_initial"),
        ("identity", "0002_seed_system_roles"),
    ]

    operations = [
        migrations.RunPython(seed_approval_permissions, remove_approval_permissions),
    ]
