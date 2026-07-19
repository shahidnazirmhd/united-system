"""Base class for domain events published by any module.

Modules communicate across their boundary either through explicit ports
(direct, synchronous calls into another module's application layer) or
through domain events (indirect, for reactive/fan-out cases like Approvals
and Notifications subscribing to events from every other module) — see
HRMS_Architecture.md section 3. This is the base type for the latter.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
