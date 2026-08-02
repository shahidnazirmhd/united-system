"""Django ORM-backed implementation of `SettingRepository`."""
from __future__ import annotations

import uuid
from typing import Any

from apps.settings.domain.entities import Setting
from apps.settings.domain.exceptions import SettingNotFoundError
from apps.settings.domain.repositories import SettingRepository
from apps.settings.infrastructure.models import SettingRecord
from shared_kernel.infrastructure.uuid7 import generate_uuid7


def _to_domain(record: SettingRecord) -> Setting:
    return Setting(id=record.id, key=record.key, value=record.value, description=record.description)


class DjangoSettingRepository(SettingRepository):
    def get_by_key(self, key: str) -> Setting | None:
        record = SettingRecord.objects.filter(key=key).first()
        return _to_domain(record) if record is not None else None

    def list_all(self) -> list[Setting]:
        return [_to_domain(record) for record in SettingRecord.objects.all().order_by("key")]

    def update_value(self, *, key: str, value: Any, updated_by: uuid.UUID | None = None) -> Setting:
        record = SettingRecord.objects.filter(key=key).first()
        if record is None:
            raise SettingNotFoundError()
        record.value = value
        record.updated_by = updated_by
        record.save(update_fields=["value", "updated_by", "updated_at"])
        return _to_domain(record)
