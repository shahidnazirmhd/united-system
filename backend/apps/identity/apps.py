from django.apps import AppConfig


class IdentityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.identity"
    label = "identity"

    def ready(self) -> None:
        """Phase 12 bugfix: subscribes to `apps.employees`'s
        `EmployeeCreated`/`EmployeeLinkedToUser` events so `User.employee_id`
        (this module's own reciprocal half of `Employee.user_id` — see
        `apps/identity/__init__.py`'s docstring) actually gets populated.
        Before this, the field existed but nothing ever wrote to it.

        Mirrors `apps.leave.apps.py`'s `ready()` exactly: importing another
        module's *event type* to subscribe to it is the one acceptable form
        of cross-module coupling for an event subscriber (depending on a
        published event, never on internals) — see that file's docstring
        for the fuller reasoning, and
        `apps/identity/interface/event_handlers.py`'s docstring for why
        Identity subscribing (rather than looking Employees up directly) is
        the only architecturally consistent fix here.

        Deferred import (inside the method): Django forbids importing
        models before the app registry is fully populated, and `ready()` is
        the documented place to register event/signal handlers for exactly
        this reason.
        """
        from apps.employees.domain.events import EmployeeCreated, EmployeeLinkedToUser
        from apps.identity.interface.event_handlers import (
            handle_employee_created,
            handle_employee_linked_to_user,
        )
        from shared_kernel.infrastructure.event_bus_impl import event_bus

        event_bus.subscribe(EmployeeCreated, handle_employee_created)
        event_bus.subscribe(EmployeeLinkedToUser, handle_employee_linked_to_user)
