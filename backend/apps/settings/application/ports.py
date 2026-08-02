"""Outbound ports for the Settings application layer.

`LeaveReferenceCheckPort` mirrors `apps.attendance.application.ports
.LeaveReferenceCheckPort` exactly — same reverse-dependency rationale (round
15 item 4 this time, not item 3): Settings must ask Leave "does any real
leave request currently depend on the configuration I'm about to change"
before allowing the Default Week Off setting to be updated, since every
active leave request's frozen `working_days` was computed against the
week-off weekday in effect when it was applied for. See that port's
docstring for the full "reverse port" reasoning — it applies here unchanged.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LeaveReferenceCheckPort(ABC):
    @abstractmethod
    def has_any_active_leave_request(self) -> bool:
        """True if any PENDING/APPROVED leave request exists at all,
        system-wide — used by `SettingsService.update_setting` to block
        changing `default_week_off` while any active request's frozen
        `working_days` still depends on the current value."""
        raise NotImplementedError
