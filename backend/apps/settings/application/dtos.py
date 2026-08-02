"""Input/output DTOs for the Settings application service."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SettingResponse:
    key: str
    value: Any
    description: str


@dataclass(frozen=True)
class UpdateSettingRequest:
    key: str
    value: Any
    updated_by: uuid.UUID | None = None
