"""Reuses Identity's `HasPermission`/`HasRole`, matching every other
module's own interface/permissions.py convention."""
from __future__ import annotations

from apps.identity.interface.permissions import HasPermission, HasRole

VIEW_ATTENDANCE = "attendance.view_attendance"
MANAGE_HOLIDAYS = "attendance.manage_holidays"

__all__ = ["HasPermission", "HasRole", "VIEW_ATTENDANCE", "MANAGE_HOLIDAYS"]
