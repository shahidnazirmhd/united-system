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
