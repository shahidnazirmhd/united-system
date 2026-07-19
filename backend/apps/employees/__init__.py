"""Employee module: the first HR business module, built on the Shared
Infrastructure delivered alongside it (shared_kernel's generic
BaseRepository/BaseService/SoftDeleteModel — see this phase's delivery
notes).

Owns the core HR profile: identity (name, contact), employment facts
(status, type, join/termination dates), and structural placement
(department, manager) — HRMS_Database_Design.md section 3.2. Deliberately
excludes anything belonging to a not-yet-built module (no salary, no
documents, no performance ratings); those modules will reference
`employee_id` as a plain UUID, exactly like this module references
`identity.users.id`, and none of them require a change here to do so.

Linked to Identity's User the same way identity.User.employee_id already
anticipated (apps/identity/domain/entities.py): `Employee.user_id` is a
nullable, unique, non-foreign-key logical reference — not every employee
has login access on day one, and not every user is an employee.
"""
