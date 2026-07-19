"""Base building block for domain entities shared across all bounded contexts.

Nothing in this file imports Django, DRF, Celery, or any other framework —
that constraint is the entire point of the domain layer being
framework-independent (HRMS_Architecture.md section 1.2). Only the Python
standard library is used here.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(kw_only=True)
class Entity:
    """Base class for all domain entities.

    Entity identity/equality is defined by `id`, not by attribute values —
    two entities with the same id are considered the same entity even if one
    is a stale in-memory copy with different field values.
    """

    id: uuid.UUID

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
