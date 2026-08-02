from __future__ import annotations

from django.apps import AppConfig


class LeaveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.leave"
    label = "leave"

    def ready(self) -> None:
        """Wires this module's cross-module integration — two entirely
        separate mechanisms, both registered here at Django app-startup
        time:

        1. Subscribes to apps.employees' `EmployeeCreated` event so a
           brand-new employee gets an initial leave balance row per active
           leave type without apps.employees ever needing to know this
           module exists. This was the first place in the codebase
           `EventBus.subscribe()` was ever called —
           `apps/employees/domain/events.py`'s docstring anticipated
           exactly this.

        2. Phase 9 (Approval Engine): registers `LeaveApprovalChainResolver`
           into `apps.approvals`'s `chain_resolver_registry`, keyed by
           `SUBJECT_TYPE_LEAVE_REQUEST` — this is how the generic engine
           learns "who approves a leave request" without ever importing
           this module. It also subscribes to `apps.approvals`'s
           `ApprovalDecided` event, so a manager's Telegram decision
           finally calls the `LeaveRequestService.approve()`/`.reject()`
           extension points Phase 8 built and left unwired.

        Importing `apps.employees.domain.events.EmployeeCreated` and
        `apps.approvals.domain.events.ApprovalDecided` here is the one
        acceptable form of cross-module coupling for an event subscriber:
        depending on another module's public *event type* to react to it,
        never on its internals. The alternative (Employees or Approvals
        depending on Leave) would be backwards and would break "new modules
        must be addable without modifying existing modules" — see
        `apps.approvals.apps.py`'s own `ready()` docstring for why that
        module's side of this wiring is deliberately empty.

        Deferred imports (inside the method, not at module level): Django
        forbids importing models before the app registry is fully populated,
        and `AppConfig.ready()` is the documented place to register signal-
        /event-handlers for exactly this reason.
        """
        from apps.approvals.application.registry import chain_resolver_registry
        from apps.approvals.domain.events import ApprovalDecided
        from apps.employees.domain.events import EmployeeCreated
        from apps.leave.infrastructure.approval_request_adapter import SUBJECT_TYPE_LEAVE_REQUEST
        from apps.leave.infrastructure.employee_lookup_adapter import EmployeeServiceLookupAdapter
        from apps.leave.infrastructure.leave_approval_chain_resolver import LeaveApprovalChainResolver
        from apps.leave.interface.event_handlers import handle_approval_decided, handle_employee_created
        from shared_kernel.infrastructure.event_bus_impl import event_bus

        event_bus.subscribe(EmployeeCreated, handle_employee_created)

        chain_resolver_registry.register(
            SUBJECT_TYPE_LEAVE_REQUEST, LeaveApprovalChainResolver(EmployeeServiceLookupAdapter())
        )
        event_bus.subscribe(ApprovalDecided, handle_approval_decided)

        # Round 14 items 6/8 — importing this module (for its side effect
        # only: the `@shared_task` decorator registers
        # `reconcile_leave_employee_statuses` into Celery's task registry)
        # is what makes the task runnable in a worker process at all.
        # `Celery.autodiscover_tasks()` (config/celery.py) only looks for a
        # top-level `<app>.tasks` module for each installed app, never a
        # nested `infrastructure/tasks.py` — every module in this codebase
        # that defines Celery tasks under `infrastructure/` needs its own
        # explicit import somewhere reached at Django startup for this
        # reason (this app's `ready()`, itself called by `django.setup()`,
        # is that place for Leave's task).
        import apps.leave.infrastructure.tasks  # noqa: F401
