"""Adapter implementing `SettingsLookupPort` against `apps.settings`'s
already-composed public `SettingsService` — same discipline as
`employee_lookup_adapter.py`'s `EmployeeServiceLookupAdapter`: this is the
one file in this module allowed to import `apps.settings`, and even then
only its public composition root, never its infrastructure directly.
"""
from __future__ import annotations

from apps.leave.application.ports import SettingsLookupPort
from apps.settings.interface import dependencies as settings_dependencies

# Matches apps.settings's own seed migration
# (apps/settings/migrations/0003_seed_default_settings.py): 0=Monday ...
# 6=Sunday, default Sunday (6). Used only if the setting row is somehow
# missing — SettingsService.get_value already degrades to a default rather
# than raising (see that method's docstring), so this is the second layer
# of the same graceful-degradation judgment, one level further out.
_FALLBACK_WEEK_OFF_WEEKDAY = 6


class SettingsServiceLookupAdapter(SettingsLookupPort):
    def get_default_week_off_weekday(self) -> int:
        value = settings_dependencies.build_settings_service().get_value(
            "default_week_off", default=_FALLBACK_WEEK_OFF_WEEKDAY
        )
        try:
            weekday = int(value)
        except (TypeError, ValueError):
            return _FALLBACK_WEEK_OFF_WEEKDAY
        return weekday if 0 <= weekday <= 6 else _FALLBACK_WEEK_OFF_WEEKDAY
