"""Employee module enumerations.

Built on shared_kernel's `BaseEnum` (shared_kernel/domain/enums.py) so the
Django model's `choices=` list is derived from these, never hand-duplicated
— see infrastructure/models.py's `EmployeeRecord.employment_status`/
`employment_type` fields. Values match HRMS_Database_Design.md's CHECK
constraints exactly (`employees.employment_status IN (...)`, `.employment_type
IN (...)`, section 6.2) — the CHECK constraint and this enum are two
independent enforcement points for the same rule, which is intentional
defense in depth, not duplication to be reconciled away.
"""
from __future__ import annotations

from shared_kernel.domain.enums import BaseEnum


class EmployeeStatus(BaseEnum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class EmploymentType(BaseEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERN = "intern"


class EmployeeCurrentStatus(BaseEnum):
    """Round 14 item 8 — a second, HR-visible "day-to-day work status"
    field, deliberately separate from `EmployeeStatus` above.
    `EmployeeStatus`/`employment_status` governs system access (can this
    employee's account be activated, can they link Telegram — see
    `Employee.activate()`/`deactivate()`/`link_telegram()`); this enum
    answers a different question entirely ("what is this person doing
    right now"), and the two fields change independently — an employee can
    be `EmployeeStatus.ACTIVE` (full system access) while
    `current_status=SICK_LEAVE` (out on approved leave) at the same time.

    SICK_LEAVE/ANNUAL_LEAVE are system-managed values: only Leave's own
    status integration may set or clear them (see
    `Employee.enter_leave_status`/`exit_leave_status` below) — an HR/Admin
    manual update (`Employee.update_current_status_manually`) can never
    choose either of these two directly. TERMINATED/RESIGNED are terminal
    for this field (mirroring `EmployeeStatus.TERMINATED`'s own one-way
    precedent) — reachable manually at any time, including while the
    employee is on an auto-managed leave status, but never left once set.
    """

    NOT_JOINED = "not_joined"
    WORKING = "working"
    SICK_LEAVE = "sick_leave"
    ANNUAL_LEAVE = "annual_leave"
    TERMINATED = "terminated"
    RESIGNED = "resigned"
