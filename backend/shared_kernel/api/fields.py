"""Reusable DRF serializer fields for optional values.

Plain `serializers.UUIDField(required=False, allow_null=True)` (or
`DateField` with the same kwargs) only accepts JSON `null` or an omitted
key as "no value" — an empty string `""` is neither, so DRF rejects it with
"Must be a valid UUID." / "Date has wrong format." Real clients regularly
send `""` for an unset optional field anyway (HTML forms, some JSON
builders, a tester leaving a Postman body field blank rather than deleting
the key), so a plain optional field is a recurring, avoidable 400/422 for
something that isn't actually a bad request.

These wrappers normalize an empty/whitespace-only string to `None` before
the base field's own validation runs, so both conventions — `null`,
omitted, or `""` — mean the same thing. This belongs in shared_kernel, not
any one module, because every future module with an optional UUID/date
field (Leave's `approved_by`, Payroll's `effective_date`, ...) hits the
identical DRF behavior.
"""
from __future__ import annotations

from typing import Any

from rest_framework import serializers


class OptionalUUIDField(serializers.UUIDField):
    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, str) and data.strip() == "":
            return None
        return super().to_internal_value(data)


class OptionalDateField(serializers.DateField):
    def to_internal_value(self, data: Any) -> Any:
        if isinstance(data, str) and data.strip() == "":
            return None
        return super().to_internal_value(data)
