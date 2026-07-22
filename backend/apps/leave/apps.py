from __future__ import annotations

from django.apps import AppConfig


class LeaveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.leave"
    label = "leave"

    def ready(self) -> None:
        """Wires the module's cross-module reactive integration: subscribes
        to apps.employees' `EmployeeCreated` event so a brand-new employee
        gets an initial leave balance row per active leave type without
        apps.employees ever needing to know this module exists.

        This is the first place in the codebase `EventBus.subscribe()` is
        actually called — `apps/employees/domain/events.py`'s docstring
        anticipated exactly this ("Future modules... will subscribe to
        EmployeeCreated... e.g. Leave provisioning an initial leave balance
        row the moment an employee is created"). Importing
        `apps.employees.domain.events.EmployeeCreated` here is the one
        acceptable form of cross-module coupling for an event subscriber:
        depending on another module's public *event type* to react to it,
        never on its internals. The alternative (Employees depending on
        Leave) would be backwards and would break "new modules must be
        addable without modifying existing modules."

        Deferred imports (inside the method, not at module level): Django
        forbids importing models before the app registry is fully populated,
        and `AppConfig.ready()` is the documented place to register signal-
        /event-handlers for exactly this reason.
        """
        from apps.employees.domain.events import EmployeeCreated
        from apps.leave.interface.event_handlers import handle_employee_created
        from shared_kernel.infrastructure.event_bus_impl import event_bus

        event_bus.subscribe(EmployeeCreated, handle_employee_created)
