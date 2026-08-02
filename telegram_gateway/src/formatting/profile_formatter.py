"""Translates `EmployeeProfile` (api_client/endpoints/employees.py) into
Telegram message text — the "My Profile" and "Employee Status" views from
the Phase 7 brief.

Pure functions, no I/O — reused by both `handlers/profile_handler.py` and
`handlers/status_handler.py`, and by the "🔄 Refresh" callback, so a display
change is a one-file edit regardless of how many commands show this data
(matches HRMS_Folder_Structure.md section 3.6's stated reason for this
package's existence).

Fields the brief asked for but that have no home in the approved DB schema
(HRMS_Database_Design.md section 3.2 — no "Company"/"Branch" columns) render
via `field_or_placeholder(None)` rather than being invented — see this
phase's delivery notes on why no schema change was made for this.
"""
from __future__ import annotations

from src.api_client.endpoints.employees import EmployeeProfile
from src.formatting.common import (
    escape_markdown,
    field_or_placeholder,
    format_current_status_label,
    format_status_label,
)

# HRMS_Database_Design.md's employees.employees table has no company/branch
# columns (single-tenant, single-site schema as approved) — these two
# fields are what the brief calls out explicitly as "if unavailable, show a
# friendly placeholder," rendered here rather than invented in the database.
_COMPANY_NAME = None
_BRANCH_NAME = None


def format_my_profile(profile: EmployeeProfile) -> str:
    lines = [
        f"*{escape_markdown(profile.full_name)}*",
        f"🆔 Employee ID: `{profile.employee_code}`",
        f"💼 Job Title: {field_or_placeholder(profile.job_title)}",
        f"🏢 Department: {field_or_placeholder(profile.department_name)}",
        f"🏬 Company: {field_or_placeholder(_COMPANY_NAME)}",
        f"📍 Branch: {field_or_placeholder(_BRANCH_NAME)}",
        f"👤 Manager: {field_or_placeholder(profile.manager_name)}",
        f"✉️ Work Email: {field_or_placeholder(profile.work_email)}",
        f"📞 Phone: {field_or_placeholder(profile.phone_number)}",
        f"📅 Joined: {field_or_placeholder(profile.date_of_joining)}",
        f"📄 Employment Type: {field_or_placeholder(profile.employment_type.replace('_', ' ').title())}",
        f"Status: {format_status_label(profile.status)}",
        # Round 15 items 7/8 — the day-to-day working status, distinct
        # from the system-access "Status" line above (see
        # formatting/common.py's `format_current_status_label` docstring).
        f"🧭 Working Status: {format_current_status_label(profile.current_status)}",
    ]
    return "\n".join(lines)


def format_employee_status(profile: EmployeeProfile) -> str:
    return (
        f"*{escape_markdown(profile.full_name)}* ({profile.employee_code})\n"
        f"Status: {format_status_label(profile.status)}\n"
        f"Working Status: {format_current_status_label(profile.current_status)}"
    )
