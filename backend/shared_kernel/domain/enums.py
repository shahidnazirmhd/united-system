"""Shared base for domain-layer enumerations.

Plain `enum.Enum`/`str` mix-in, not Django's `models.TextChoices` — the
domain layer stays framework-independent (no Django import here), exactly
like every other file in shared_kernel/domain. A module's infrastructure
layer builds its Django field `choices=` from the same enum instead of
hand-duplicating the list of values, so the two can never drift apart (see
apps/employees/infrastructure/models.py for the concrete usage).
"""
from __future__ import annotations

from enum import Enum


class BaseEnum(str, Enum):
    """Inherit as `class MyEnum(BaseEnum): FOO = "foo"`.

    Being a `str` subclass means values compare and serialize (JSON, Django
    field storage) as plain strings — `MyEnum.FOO == "foo"` is `True` — while
    still getting `Enum`'s membership checks and IDE-visible member list.
    """

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        """`(value, human_label)` pairs, suitable for a Django field's
        `choices=` kwarg. Label is the member name, title-cased with
        underscores turned to spaces — e.g. `ON_LEAVE` -> "On Leave".
        """
        return [(member.value, member.name.replace("_", " ").title()) for member in cls]

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]
