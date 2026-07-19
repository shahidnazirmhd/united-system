"""Value objects shared across modules' domain layers.

Value objects are immutable and compared by value, not identity — two
`Money(Decimal("10.00"), "USD")` instances are equal regardless of where
each came from. Module-specific value objects (e.g. Leave's `LeaveType`)
belong in that module's own `domain/value_objects.py`, not here — only
concepts genuinely shared by multiple future modules (Money by Payroll and
Leave; DateRange by Leave, Attendance, and Performance; Email, promoted here
in Phase 6 once Employee needed the same validation Identity already had)
belong in this shared file.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Email:
    """Normalizes to lowercase on construction so uniqueness and lookups are
    case-insensitive without depending on a database-specific column type
    (HRMS_Database_Design.md speced `CITEXT` for `employees.work_email`;
    this project uses a plain unique column plus this normalization instead,
    for the same reason `identity.users.email` does — see this value
    object's original introduction in apps/identity's delivery notes).

    Originally lived in apps/identity/domain/value_objects.py; promoted here
    in Phase 6 once apps/employees needed the identical validation for
    `work_email`/`personal_email` — identity re-exports this class from its
    own module (`from shared_kernel.domain.value_objects import Email`) so
    no other file in identity had to change.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or "@" not in self.value:
            raise ValueError(f"'{self.value}' is not a valid email address")
        object.__setattr__(self, "value", self.value.strip().lower())

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        if self.amount != self.amount.quantize(Decimal("0.01")):
            raise ValueError("Money amount must not have more than 2 decimal places")

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def _assert_same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError(
                f"Cannot operate on Money in different currencies: "
                f"{self.currency} vs {other.currency}"
            )


@dataclass(frozen=True)
class DateRange:
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")

    def overlaps(self, other: "DateRange") -> bool:
        return self.start_date <= other.end_date and other.start_date <= self.end_date

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1
