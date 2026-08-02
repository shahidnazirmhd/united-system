"""Domain entity for Settings: a single key-value application setting.

Plain Python, no Django — matching every other module's domain layer.
Unlike most aggregate roots in this codebase, callers address a `Setting`
by its `key` (a stable, human-chosen string), not by `id` — `id` still
exists (every `Entity` has one, and the ORM row needs a primary key) but is
never part of this module's own public contract; see
`domain/repositories.py`'s `SettingRepository.get_by_key`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared_kernel.domain.base_entity import Entity


@dataclass(kw_only=True)
class Setting(Entity):
    key: str
    value: Any
    description: str = ""
