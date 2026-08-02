"""Round 14 items 6/8 — the plain-string contract between a `LeaveType`'s
`maps_to_employee_status` and Employees' `EmployeeCurrentStatus` enum.

Deliberately plain strings, not an imported
`apps.employees.domain.enums.EmployeeCurrentStatus` — this module's domain
layer never imports another module's domain layer (the same rule
`domain/exceptions.py`'s `LeaveEmployeeNotFoundError` docstring states).
The two systems of values are kept in sync by convention (these strings
are exactly `EmployeeCurrentStatus.SICK_LEAVE.value`/`.ANNUAL_LEAVE.value`
on the other side of `EmployeeStatusPort`), the same way `subject_type`
strings are kept in sync between this module and `apps.approvals` without
either importing the other's enum.
"""
from __future__ import annotations

ALLOWED_EMPLOYEE_STATUS_MAPPINGS = frozenset({"sick_leave", "annual_leave"})
