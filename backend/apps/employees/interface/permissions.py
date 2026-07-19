"""Employee module deliberately does not define new permission *classes* —
it reuses Identity's `HasPermission`/`HasRole`
(apps/identity/interface/permissions.py), exactly as that module's own
docstring says every future module is expected to: "the one place other
modules are expected to import from."

What this file adds is this module's own permission *code* constants, so
the one place that must stay in sync with
apps/employees/migrations/0002_seed_employee_permissions.py's seeded codes
is a single source of truth for the interface layer, rather than the
literal string "employees.manage_employees" appearing in every view that
needs it. (The migration itself still hardcodes the literal strings rather
than importing this module — Django migrations must never import
application code, so they can stay stable even if this file changes later.)
"""
from __future__ import annotations

from apps.identity.interface.permissions import HasPermission, HasRole

VIEW_EMPLOYEES = "employees.view_employees"
MANAGE_EMPLOYEES = "employees.manage_employees"

__all__ = ["HasPermission", "HasRole", "VIEW_EMPLOYEES", "MANAGE_EMPLOYEES"]
