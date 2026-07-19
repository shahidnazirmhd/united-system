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
