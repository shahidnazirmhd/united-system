"""Repository interface for Settings.

Deliberately NOT built on shared_kernel's generic `BaseRepository`
(get_by_id/list/create/update/delete keyed by UUID `id`) — every real
caller of this module addresses a setting by its `key`, never its `id`
(see domain/entities.py's docstring), so a `get_by_id`-shaped contract
would be dead code here. A small, hand-written ABC (matching Identity's
original pre-`BaseRepository` style) is the honest shape for this module.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from apps.settings.domain.entities import Setting


class SettingRepository(ABC):
    @abstractmethod
    def get_by_key(self, key: str) -> Setting | None:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Setting]:
        raise NotImplementedError

    @abstractmethod
    def update_value(self, *, key: str, value: Any, updated_by: Any = None) -> Setting:
        """Overwrites the value of an already-seeded setting. Never creates
        a new row — see `SettingNotFoundError`'s docstring for why this
        module has no create path of its own."""
        raise NotImplementedError
