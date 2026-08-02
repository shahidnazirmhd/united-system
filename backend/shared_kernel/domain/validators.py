"""Small, reusable domain-layer validation functions.

These exist for validation rules genuinely common across modules' value
objects (non-blank text, length limits, non-negative numbers) — the same
category of "shared because more than one module needs it" as
value_objects.py's Money/DateRange. Module-specific business rules (e.g.
"last_working_date must not precede date_of_joining") stay in that module's
own value objects/entities, not here.

Every function raises shared_kernel's ValidationError on failure, not a
bare ValueError — value objects that call these still raise ValueError from
their own __post_init__ for rules that are entirely local to them (matching
the existing convention in shared_kernel/domain/value_objects.py and
apps/identity/domain/value_objects.py), but a module can choose to call
these helpers and let the ValidationError surface directly through
shared_kernel/api/exception_handler.py when it wants the standard
`422 validation_error` envelope without wrapping it itself.
"""
from __future__ import annotations

from shared_kernel.api.exceptions import ValidationError


def validate_not_blank(value: str, *, field_name: str) -> str:
    if not value or not value.strip():
        raise ValidationError(f"'{field_name}' must not be blank.")
    return value


def validate_max_length(value: str, max_length: int, *, field_name: str) -> str:
    if len(value) > max_length:
        raise ValidationError(f"'{field_name}' must be at most {max_length} characters.")
    return value


def validate_non_negative(value: int | float, *, field_name: str) -> int | float:
    if value < 0:
        raise ValidationError(f"'{field_name}' must not be negative.")
    return value
