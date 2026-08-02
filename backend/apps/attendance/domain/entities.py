"""Domain entity for Attendance: Holiday.

Plain Python, no Django — matching every other module's domain layer. See
this module's own `__init__.py` docstring for why Holiday is Attendance's
first entity, ahead of real attendance tracking itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from shared_kernel.domain.base_entity import Entity


@dataclass(kw_only=True)
class Holiday(Entity):
    name: str
    holiday_date: date
    description: str = ""
    is_active: bool = True
