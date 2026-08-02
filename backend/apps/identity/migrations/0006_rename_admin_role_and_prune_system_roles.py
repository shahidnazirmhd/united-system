"""Data migration (Role & Permission Management phase): reduces the system
role set seeded by 0002_seed_system_roles.py down to a single built-in role.

Product decision: only one role now ships built-in — "Admin" (every other
role — Manager, Payroll Admin, Recruiter, or anything else — is created and
managed by an Admin from the Role Management UI going forward, not seeded).

Two operations:

1. Rename "HR Admin" -> "Admin", in place (same RoleRecord row/id). This is
   an UPDATE, not a delete-and-recreate, specifically so every permission
   already granted to "HR Admin" — by this app's own 0002 migration AND by
   apps.employees/apps.leave/apps.approvals's own 0002 permission-seeding
   migrations (which grant to "HR Admin" by name, reached only through
   Django's historical model API, never a code import) — carries over to
   "Admin" automatically. No other app's migration needs to change.

2. Delete the "Employee", "Manager", "Payroll Admin", and "Recruiter" system
   role rows outright. `on_delete=CASCADE` on UserRoleRecord/
   RolePermissionRecord means any permission grants or user assignments
   those roles held disappear with them — intended, since they're no longer
   builtin roles at all. (In practice only "Manager" ever had grants —
   employees/leave/approvals's read-only grants to it — Payroll Admin and
   Recruiter were pure placeholders for modules that don't exist yet.)

Why this migration depends on employees.0002/leave.0002/approvals.0002
(below), even though apps.identity has no code/runtime dependency on any of
them: those three migrations each do `RoleRecord.objects.get(name="HR
Admin")` at the time *they* run, to grant their own module's permissions to
it. On a brand-new database, if this migration's rename ran first, "HR
Admin" would no longer exist under that name and those lookups would raise
`RoleRecord.DoesNotExist` (each catches it and skips the grant — see their
own "defensive only" comments — so nothing would crash, but the new "Admin"
role would silently end up missing employees.manage_employees/
leave.manage_leave/approvals.decide_approvals on a fresh install). Declaring
these dependencies is a migration-graph-only ordering edge — it does not
import any other app's code — and is the narrow, correct way to guarantee
those grants land on "HR Admin" before it becomes "Admin", for both existing
databases (where they're already applied and this is a no-op) and fresh
ones.

Reversible on a best-effort basis: renames "Admin" back to "HR Admin" and
re-seeds empty (no-permission) rows for the four removed roles. It cannot
restore exactly which permissions/users those roles held before forward
ran — same limitation every reverse migration in this codebase already
accepts (see 0002's own module docstring: "the reverse migration removes
exactly what forward created", which for a rename is inherently lossy on
the way back).
"""
from __future__ import annotations

from django.db import migrations

RENAMED_FROM = "HR Admin"
RENAMED_TO = "Admin"

REMOVED_SYSTEM_ROLES = [
    {"name": "Employee", "description": "Baseline role held by every authenticated employee."},
    {"name": "Manager", "description": "Manages a team of direct reports."},
    {"name": "Payroll Admin", "description": "Administers payroll runs and compensation data."},
    {"name": "Recruiter", "description": "Manages job openings and candidates."},
]


def rename_and_prune_roles(apps, schema_editor):
    RoleRecord = apps.get_model("identity", "RoleRecord")

    RoleRecord.objects.filter(name=RENAMED_FROM, is_system_role=True).update(name=RENAMED_TO)

    RoleRecord.objects.filter(
        name__in=[r["name"] for r in REMOVED_SYSTEM_ROLES], is_system_role=True
    ).delete()


def restore_roles(apps, schema_editor):
    RoleRecord = apps.get_model("identity", "RoleRecord")

    RoleRecord.objects.filter(name=RENAMED_TO, is_system_role=True).update(name=RENAMED_FROM)

    for role in REMOVED_SYSTEM_ROLES:
        RoleRecord.objects.get_or_create(
            name=role["name"], defaults={"description": role["description"], "is_system_role": True}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0005_remove_is_system_account"),
        # Ordering-only — see module docstring. Not a code/runtime dependency.
        ("employees", "0002_seed_employee_permissions"),
        ("leave", "0002_seed_leave_permissions"),
        ("approvals", "0002_seed_approval_permissions"),
    ]

    operations = [
        migrations.RunPython(rename_and_prune_roles, restore_roles),
    ]
