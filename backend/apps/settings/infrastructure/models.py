"""Django ORM model for Settings.

Named with a "Record" suffix, matching every other module's convention.
`value` is a `JSONField` so any future setting's shape (bool, int, string,
list of strings, small object) fits without a schema change — the
trade-off, documented once here rather than at every call site, is that
this module does no shape validation of its own beyond "is this valid
JSON": a consuming module's own port/adapter (e.g. Leave's
SettingsLookupPort) is responsible for interpreting/validating the value
it reads for the specific key it cares about.
"""
from __future__ import annotations

from django.db import models

from shared_kernel.infrastructure.base_models import BaseModel


class SettingRecord(BaseModel):
    key = models.CharField(max_length=100, unique=True)
    value = models.JSONField()
    description = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "app_settings"

    def __str__(self) -> str:
        return f"{self.key}={self.value!r}"
