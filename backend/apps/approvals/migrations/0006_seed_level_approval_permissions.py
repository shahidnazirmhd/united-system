"""Data migration: registers the two new, engine-level (not Leave-specific)
"which level may you decide from the HR web system" permission codes
introduced by the Approval Workflow Changes v2 round, and grants a
sensible default role — same discipline as
`apps/approvals/migrations/0002_seed_approval_permissions.py`.

These live in `apps.approvals` (module="approvals"), not `apps.leave`,
specifically so any future subject module reusing this engine's two-level
pattern can reuse the same two codes instead of inventing its own —
`apps.leave.infrastructure.leave_approval_chain_resolver` is simply the
first (and so far only) resolver to actually reference them.

* `approvals.level1_approve` — required, on the WEB channel specifically,
  to decide a dual-mode step's current level (e.g. Leave's level 1) — via
  Telegram, identity alone still governs, this permission is irrelevant
  there.
* `approvals.level2_approve` — required to decide a permission-based final
  level (e.g. Leave's level 2) from the web. Replaces `leave.manage_leave`
  for this one purpose (deciding the approval step itself) — deliberately
  a SEPARATE permission from `leave.manage_leave`, which continues to gate
  Leave's own management screens (types, balances, the HR queue) and
  nothing about deciding an approval.

Default grant — "Admin" only, NOT "Manager" or "HR Admin": as of
`identity/migrations/0006_rename_admin_role_and_prune_system_roles.py`,
"Admin" is the ONLY system role this codebase still seeds by default — "HR
Admin" was renamed to it (carrying its existing grants over) and "Manager"
(among others) was deleted outright. Granting to "Manager" here the way
`apps/leave/migrations/0002_seed_leave_permissions.py`/
`apps/approvals/migrations/0002_seed_approval_permissions.py` historically
did would be dead on arrival on any fresh install — that role no longer
exists to receive it. Both new permissions are therefore granted to
"Admin" instead, so a fresh install can immediately decide both levels
from the web without any manual setup; per this round's explicit "do not
hardcode users or roles for approval access" requirement, an admin who
later creates their own "Manager" (or equivalent) role via Role & Permission
Management is expected to grant `approvals.level1_approve` to it themselves
— this migration cannot do that for a role that doesn't exist yet.

Depends on `identity.0006` specifically (not just `identity.0002`) so that
the "Admin" role already exists UNDER THAT NAME by the time this runs —
depending only on `0002` would risk this migration executing before the
rename, when the role was still named "HR Admin".

Reaches into identity's tables only via Django's historical model API,
never imports apps.identity's application code.
"""
from __future__ import annotations

from django.db import migrations

LEVEL_APPROVAL_PERMISSIONS = [
    {
        "code": "approvals.level1_approve",
        "description": "Approve or reject a Level 1 (first-stage) approval step from the HR system.",
    },
    {
        "code": "approvals.level2_approve",
        "description": "Approve or reject a Level 2 (final-stage) approval step from the HR system.",
    },
]

ROLE_PERMISSION_GRANTS = {
    "Admin": ["approvals.level1_approve", "approvals.level2_approve"],
}


def seed_level_approval_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    RoleRecord = apps.get_model("identity", "RoleRecord")
    RolePermissionRecord = apps.get_model("identity", "RolePermissionRecord")

    permissions_by_code = {}
    for perm in LEVEL_APPROVAL_PERMISSIONS:
        record, _ = PermissionRecord.objects.get_or_create(
            code=perm["code"], defaults={"description": perm["description"], "module": "approvals"}
        )
        permissions_by_code[perm["code"]] = record

    for role_name, codes in ROLE_PERMISSION_GRANTS.items():
        try:
            role_record = RoleRecord.objects.get(name=role_name)
        except RoleRecord.DoesNotExist:
            # Defensive only — this migration's dependency on identity.0006
            # guarantees "Admin" exists under that name by the time this
            # runs, on any database that migrates from scratch. An existing
            # database that has somehow renamed/removed "Admin" itself
            # would hit this — the permission rows above still get
            # registered either way, just with no default grant.
            continue
        for code in codes:
            RolePermissionRecord.objects.get_or_create(
                role=role_record, permission=permissions_by_code[code]
            )


def remove_level_approval_permissions(apps, schema_editor):
    PermissionRecord = apps.get_model("identity", "PermissionRecord")
    PermissionRecord.objects.filter(code__in=[p["code"] for p in LEVEL_APPROVAL_PERMISSIONS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("approvals", "0005_approval_step_dual_mode_and_decided_by"),
        ("identity", "0006_rename_admin_role_and_prune_system_roles"),
    ]

    operations = [
        migrations.RunPython(seed_level_approval_permissions, remove_level_approval_permissions),
    ]
