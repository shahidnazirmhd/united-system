"""One-time data repair for the Phase 12 bugfix: re-syncs
`identity.User.employee_id` for every `Employee` that already has a
`user_id` set from *before* `apps.identity` had any event subscription to
populate it.

Why this is needed: `Employee.user_id` and `User.employee_id` are two
independent, non-foreign-key fields kept in sync purely by
`apps.employees` publishing events apps.identity subscribes to (see
`apps/identity/interface/event_handlers.py`'s docstring). That subscription
did not exist until this bugfix, so any employee-to-user link made before
today (including data seeded directly, e.g. via `create_admin_user` +
manually setting `user_id`) never reached Identity's side. New links made
from now on sync automatically; this command is only for links that
already existed.

Deliberately reuses the exact same event (`EmployeeLinkedToUser`) Identity
already subscribes to, rather than writing new sync logic here — running
this command is equivalent to "pretend every already-linked employee was
just linked again right now." Safe to run more than once (the handler is
an idempotent upsert of one field).

Usage:
    python manage.py backfill_user_employee_links
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.employees.domain.events import EmployeeLinkedToUser
from apps.employees.infrastructure.models import EmployeeRecord
from shared_kernel.infrastructure.event_bus_impl import event_bus


class Command(BaseCommand):
    help = "Re-syncs identity.User.employee_id for every already-linked Employee."

    def handle(self, *args, **options) -> None:
        linked_employees = EmployeeRecord.objects.exclude(user_id__isnull=True)
        count = 0
        for employee in linked_employees:
            event_bus.publish(EmployeeLinkedToUser(employee_id=employee.id, user_id=employee.user_id))
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Re-synced {count} employee-user link(s)."))
