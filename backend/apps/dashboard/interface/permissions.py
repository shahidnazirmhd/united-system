"""Dashboard mints no new permission codes of its own — every widget's
visibility is gated by the permission code that already governs reading
the same data through its own module's endpoints. Re-exported here so
`interface/views.py` has one place to import from, matching every other
module's own `interface/permissions.py` convention (see
`apps.employees.interface.permissions`'s docstring for the full reasoning).
"""
from __future__ import annotations

from apps.attendance.interface.permissions import VIEW_ATTENDANCE
from apps.employees.interface.permissions import VIEW_EMPLOYEES
from apps.identity.interface.permissions import HasPermission, HasRole
from apps.leave.interface.permissions import VIEW_LEAVE

__all__ = [
    "HasPermission",
    "HasRole",
    "VIEW_EMPLOYEES",
    "VIEW_LEAVE",
    "VIEW_ATTENDANCE",
]
