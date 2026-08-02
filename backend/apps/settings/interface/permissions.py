"""Reuses Identity's `HasPermission`/`HasRole`, matching every other
module's own interface/permissions.py convention — see
apps/employees/interface/permissions.py's docstring."""
from __future__ import annotations

from apps.identity.interface.permissions import HasPermission, HasRole

VIEW_SETTINGS = "settings.view_settings"
MANAGE_SETTINGS = "settings.manage_settings"

__all__ = ["HasPermission", "HasRole", "VIEW_SETTINGS", "MANAGE_SETTINGS"]
