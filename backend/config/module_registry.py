"""Single source of truth for which Django apps are active.

This is the concrete mechanism behind "new HR modules must be addable
without modifying existing modules" (PROJECT_SPEC.md). Adding a module means
adding its entry here — nothing else changes:

- `ACTIVE_MODULES` feeds `INSTALLED_APPS` (config/settings/base.py) and
  Celery's task autodiscovery (config/celery.py).
- `API_MODULE_URL_PREFIXES` feeds the versioned `/api/v1/` router
  (config/urls.py). Health/ops endpoints are intentionally kept out of this
  dict and wired directly in urls.py, since they sit outside API versioning
  by convention (a load balancer's liveness probe doesn't care about API
  versions).

`apps.identity` is the first real module: authentication and RBAC. It is
deliberately not an "HR business module" in the PROJECT_SPEC.md sense (no
Employee/Leave/Attendance/Payroll logic lives in it) — see
apps/identity's own module docstring for why User and Employee are kept
separate. `apps.healthcheck` is a system utility, not a business module
either, which is why it was here from the start.

`apps.employees` is the first HR business module (Phase 6) — it depends on
`apps.identity` (its permission seed migration reaches into identity's
tables, and `Employee.user_id` is a logical reference to `identity.users`)
but nothing in `apps.identity` was modified to add it, and nothing above
this dict needed to change either.

`apps.leave` is the second HR business module (Phase 8) — it depends on
`apps.identity` (its own permission seed migration) and on `apps.employees`
(through `apps.leave.application.ports.EmployeeLookupPort`, an adapter onto
`apps.employees`'s already-composed public `EmployeeService`, never that
module's infrastructure directly), but neither `apps.identity` nor
`apps.employees` needed a single line changed to support it.
"""
from __future__ import annotations

ACTIVE_MODULES: list[str] = [
    "apps.healthcheck",
    "apps.identity",
    "apps.employees",
    "apps.leave",
    # Future HR modules are added here, one line each, e.g.:
    # "apps.attendance",
    # "apps.payroll",
    # "apps.performance",
    # "apps.recruitment",
    # "apps.approvals",
    # "apps.notifications",
]

API_MODULE_URL_PREFIXES: dict[str, str] = {
    "auth": "apps.identity",
    "employees": "apps.employees",
    "leave": "apps.leave",
}
