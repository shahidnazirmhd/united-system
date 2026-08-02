"""Subscribers for events this module reacts to:
`apps.employees.domain.events.EmployeeCreated` and
`apps.employees.domain.events.EmployeeLinkedToUser`.

Registered by `apps/identity/apps.py`'s `ready()` hook — the exact same
pattern `apps.leave.interface.event_handlers`/`apps.leave.apps.py` already
established for reacting to `EmployeeCreated` (see that module's docstring).
This is the *only* place `apps.identity` imports anything from
`apps.employees`, and even here only its public event *types* (dataclasses
with no behavior), never its domain/infrastructure/models — the same rule
`apps.leave.apps.py`'s own docstring documents.

Why this exists: `User.employee_id` and `Employee.user_id` are two
independent, non-foreign-key fields (see `apps/identity/__init__.py`'s
docstring) — Employee owns the write (`user_id` is set at creation or via
`POST /employees/{id}/link-user/`), and Identity's `employee_id` is meant to
be a reciprocal, denormalized mirror of that fact, updated whenever
Employees announces a link. Before this bugfix, nothing ever populated it —
`apps.identity` had a `ready()` with no event subscription at all, and its
own `application/ports.py` explicitly documents that Identity must never
*pull* this information by looking up Employees directly (that port was
deliberately removed in an earlier refactor). The fix has to be Employees
*pushing* the fact via an event, which is what these two handlers receive.
"""
from __future__ import annotations

import logging
import uuid

from apps.employees.domain.events import EmployeeCreated, EmployeeLinkedToUser
from apps.identity.infrastructure.repositories import DjangoUserRepository

logger = logging.getLogger(__name__)


def _link_user_to_employee(*, user_id: uuid.UUID, employee_id: uuid.UUID) -> None:
    users = DjangoUserRepository()
    user = users.get_by_id(user_id)
    if user is None:
        # The user_id on the Employee side doesn't (or no longer) resolve to
        # a real User — nothing to do. Not logged as an error: this is a
        # legitimate state if a User was somehow removed after linking (no
        # delete endpoint exists today, but defensive regardless).
        logger.warning(
            "Employee %s links to user_id=%s, but no such User exists — skipping employee_id sync.",
            employee_id,
            user_id,
        )
        return
    users.save(user.with_employee(employee_id=employee_id))


def handle_employee_created(event: EmployeeCreated) -> None:
    """An employee can be created already linked to a user (`user_id` set
    at `POST /employees/`) — if so, sync it here. Most employees are
    created with no `user_id` at all, in which case this is a no-op."""
    if event.user_id is None:
        return
    _link_user_to_employee(user_id=event.user_id, employee_id=event.employee_id)


def handle_employee_linked_to_user(event: EmployeeLinkedToUser) -> None:
    """An existing employee was linked to an existing user after the fact,
    via `POST /employees/{id}/link-user/` — always has both ids present."""
    _link_user_to_employee(user_id=event.user_id, employee_id=event.employee_id)
