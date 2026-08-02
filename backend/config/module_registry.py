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

`apps.approvals` (Phase 9) is a generic, subject-agnostic Approval Engine —
it depends on `apps.identity` (its own permission seed migration) and on
`apps.employees` (through its own `EmployeeLookupPort` adapter, same
pattern as `apps.leave`'s), but knows nothing about `apps.leave` or any
other subject module at all. The dependency instead runs the other way for
consumption: `apps.leave` depends directly on `apps.approvals` (calling
`ApprovalService.create_approval_request` right after creating a
`LeaveRequest`) and registers its own `ApprovalChainResolverPort`
implementation into `apps.approvals.application.registry
.chain_resolver_registry` at startup (`apps/leave/apps.py`'s `ready()`) —
`apps.approvals` itself never imports `apps.leave`, so a second, third, or
Nth subject module can adopt this engine later with zero changes to it.

`apps.settings` (round 14) is a generic key-value application-settings
store — no dependency on any other module at all. `apps.attendance`
(round 14) starts with Holiday Management only; like `apps.employees`'
`Department`, it has no dependency on anything either. Both are consumed
by `apps.leave` through their own read-only ports
(`SettingsLookupPort`/`HolidayLookupPort` in
`apps.leave.application.ports`), the same "the consumer owns the port"
rule `EmployeeLookupPort` already established — neither `apps.settings`
nor `apps.attendance` needed a single line changed to support it. Note
the app label for Settings is `app_settings`, not `settings` — see
`apps/settings/apps.py`, chosen to avoid any ambiguity with Django's own
`django.conf.settings` in log output, migration names, and `apps.get_model`
calls; the URL prefix and Python package path are unaffected and remain
`apps.settings`/`/api/v1/settings/`.

`apps.dashboard` (Phase 14) is a pure read-aggregator with no database
table of its own (no `models.py`, no `migrations/` package — the first such
module here). It depends on `apps.employees`, `apps.leave`, and
`apps.attendance` through its own read-only ports
(`EmployeeStatisticsPort`/`LeaveStatisticsPort`/`HolidayLookupPort` in
`apps.dashboard.application.ports`), the same "the consumer owns the port"
rule every prior cross-module read in this codebase already follows — none
of those three modules needed a single line changed to support it beyond
each module's own additive `get_statistics`/`list_upcoming` read method
(added because each module owns the decision of what its own statistics
mean, not Dashboard).
"""
from __future__ import annotations

ACTIVE_MODULES: list[str] = [
    "apps.healthcheck",
    "apps.identity",
    "apps.employees",
    "apps.leave",
    "apps.approvals",
    "apps.settings",
    "apps.attendance",
    "apps.dashboard",
    # Future HR modules are added here, one line each, e.g.:
    # "apps.payroll",
    # "apps.performance",
    # "apps.recruitment",
    # "apps.notifications",
]

API_MODULE_URL_PREFIXES: dict[str, str] = {
    "auth": "apps.identity",
    "employees": "apps.employees",
    "leave": "apps.leave",
    "approvals": "apps.approvals",
    "settings": "apps.settings",
    "attendance": "apps.attendance",
    "dashboard": "apps.dashboard",
}
