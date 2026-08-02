"""Shared formatting helpers reused across formatters — per
HRMS_Folder_Structure.md section 3.6, deliberately isolated so a display
change never requires touching the handler logic that fetches the data.
"""
from __future__ import annotations

_UNAVAILABLE_PLACEHOLDER = "_Not available_"


def field_or_placeholder(value: str | None) -> str:
    """Every "friendly placeholder for unavailable fields" the Phase 7
    brief asks for goes through this one function, so the placeholder text
    only needs to change in one place."""
    if value is None or not value.strip():
        return _UNAVAILABLE_PLACEHOLDER
    return escape_markdown(value)


def escape_markdown(text: str) -> str:
    """Escapes Telegram legacy-Markdown's special characters so employee
    data (names, job titles) can never accidentally break message
    formatting or be mistaken for Markdown syntax."""
    for char in ("_", "*", "`", "["):
        text = text.replace(char, f"\\{char}")
    return text


_STATUS_LABELS = {
    "active": "🟢 Active",
    "on_leave": "🟡 On Leave",
    "suspended": "🔴 Suspended",
    "terminated": "⚫ Terminated",
}


def format_status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status.replace("_", " ").title())


# Round 15 items 7/8 — mirrors
# frontend/src/modules/employees/types/employee.types.ts's
# `CURRENT_STATUS_LABELS` (same six `EmployeeCurrentStatus` values), just
# with the emoji-prefixed styling this Gateway's own `_STATUS_LABELS` above
# already uses for the older `status` field. A separate map from
# `_STATUS_LABELS` on purpose — `current_status` (day-to-day working
# status: not_joined/working/sick_leave/annual_leave/terminated/resigned)
# and `status` (system-access status: active/on_leave/suspended/terminated)
# are distinct fields with distinct value sets (see
# apps.employees.domain.entities' own docstrings for that distinction).
_CURRENT_STATUS_LABELS = {
    "not_joined": "⚪ Not Joined",
    "working": "🟢 Working",
    "sick_leave": "🟡 Sick Leave",
    "annual_leave": "🟡 Annual Leave",
    "terminated": "⚫ Terminated",
    "resigned": "⚫ Resigned",
}


def format_current_status_label(current_status: str) -> str:
    return _CURRENT_STATUS_LABELS.get(current_status, current_status.replace("_", " ").title())
