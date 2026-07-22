"""Leave module deliberately does not define new permission *classes* — it
reuses Identity's `HasPermission`/`HasRole`, exactly like
`apps.employees.interface.permissions` already does (see that file's
docstring for the full reasoning; not repeated module by module).

What this file adds is this module's own permission *code* constants, kept
in sync with `apps/leave/migrations/0002_seed_leave_permissions.py`'s
seeded codes.
"""
from __future__ import annotations

from apps.identity.interface.permissions import HasPermission, HasRole

VIEW_LEAVE = "leave.view_leave"
MANAGE_LEAVE = "leave.manage_leave"

__all__ = ["HasPermission", "HasRole", "VIEW_LEAVE", "MANAGE_LEAVE"]
