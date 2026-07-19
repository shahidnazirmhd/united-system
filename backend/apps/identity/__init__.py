"""Identity module: authentication (JWT login/logout/refresh, password
reset) and authorization (RBAC roles/permissions).

User and Employee are deliberately separate entities, one-to-one and
optional on both sides (identity.User.employee_id is a nullable, unique,
non-foreign-key logical reference to a future employees.Employee row):

    User                          Employee
     |- email                      |- employee_code
     |- password_hash              |- name
     |- roles                      |- department
     |- permissions                |- leave_balance
     |                             |- attendance
     `--- one-to-one, optional --->|- etc.

Not every user needs to be an employee (system/service accounts, external
auditors, consultants), and not every employee necessarily has login access
on day one. Keeping authentication concerns entirely out of the Employee
module (apps/employees, Phase 6) — and HR data entirely out of this one —
means either can change shape without the other needing a migration.
apps.employees.domain.entities.Employee.user_id is the reciprocal side of
this module's employee_id field.
"""
