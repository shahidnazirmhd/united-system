"""Domain events published by the Leave module.

Published today with no subscriber required to exist yet — same "publish
now, subscribe later" discipline `apps/employees/domain/events.py` already
established (see `shared_kernel/infrastructure/event_bus_impl.py`'s
docstring). The Approval module, once built, is the natural future
subscriber to `LeaveRequestApplied` (to open a workflow) and the Audit/
Notifications concerns are natural future subscribers to all four.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from shared_kernel.domain.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class LeaveRequestApplied(DomainEvent):
    leave_request_id: uuid.UUID
    employee_id: uuid.UUID
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date


@dataclass(frozen=True, kw_only=True)
class LeaveRequestCancelled(DomainEvent):
    leave_request_id: uuid.UUID
    employee_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class LeaveRequestApproved(DomainEvent):
    """Not published by any code this phase (nothing calls
    `LeaveRequestService.approve()` yet) — declared now so the future
    Approval module's integration doesn't require adding a new event type
    to this file, only a new caller."""

    leave_request_id: uuid.UUID
    employee_id: uuid.UUID
    approved_by: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class LeaveRequestRejected(DomainEvent):
    leave_request_id: uuid.UUID
    employee_id: uuid.UUID
