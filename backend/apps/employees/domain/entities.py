"""Domain entities for Employees: Employee (aggregate root) and Department.

Plain Python, no Django — matching Identity's entities.py precedent. The
Django ORM models that persist these (infrastructure/models.py) are a
separate, deliberately distinct set of classes; only
infrastructure/repositories.py translates between the two.

`Department` is not in this phase's requested model list, but
`Employee.employment_info.department_id` was already approved in
HRMS_Database_Design.md as a real foreign key (same schema as Employee,
unlike identity/employees cross-module references) — a real FK needs a
real table to point at. It's implemented here minimally: no REST API of
its own this phase (out of the requested scope), just enough for
`Employee` to reference and for a repository to validate existence against.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from apps.employees.domain.enums import EmployeeStatus
from apps.employees.domain.value_objects import ContactInformation, EmployeeProfile, EmploymentInformation
from shared_kernel.domain.base_entity import Entity


@dataclass(kw_only=True)
class Department(Entity):
    name: str
    code: str
    parent_department_id: uuid.UUID | None = None
    head_employee_id: uuid.UUID | None = None
    is_active: bool = True


@dataclass(kw_only=True)
class Employee(Entity):
    employee_code: str
    # Logical reference to identity.users.id — plain UUID, never a
    # ForeignKey, per HRMS_Database_Design.md section 5 (no cross-module
    # foreign keys). Nullable and unique: not every employee has login
    # access, and a user has at most one linked employee profile — the
    # reciprocal of identity.User.employee_id
    # (apps/identity/domain/entities.py).
    user_id: uuid.UUID | None = None
    profile: EmployeeProfile
    contact_info: ContactInformation
    employment_info: EmploymentInformation
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    # Employee & Telegram Authentication refactor: the permanent link
    # between this Employee and their Telegram account, stored directly on
    # the aggregate — never via an identity.User/JWT. `telegram_user_id` is
    # what every future Telegram request is identified by (see
    # infrastructure/repositories.py's get_by_telegram_user_id); the other
    # three fields are informational (chat_id needed to push future bot
    # messages, telegram_username for display, telegram_linked_at for
    # audit/"linked since" display). All four are None until link_telegram()
    # is called, and all four are cleared together by unlink_telegram() —
    # they are never independently partially set.
    telegram_user_id: int | None = None
    telegram_chat_id: int | None = None
    telegram_username: str | None = None
    telegram_linked_at: datetime | None = None

    @property
    def is_linked_to_telegram(self) -> bool:
        return self.telegram_user_id is not None

    def link_telegram(
        self,
        *,
        telegram_user_id: int,
        chat_id: int,
        telegram_username: str | None,
        linked_at: datetime,
    ) -> "Employee":
        """Completes Telegram linking after OTP verification
        (application/services/employee_telegram_linking_service.py). Does
        NOT check "already linked to a different employee" —
        uniqueness of telegram_user_id across all employees is a
        repository-wide constraint (see DuplicateTelegramLinkError),
        checked by the service against the whole repository, not something
        a single Employee instance can verify about its peers. Re-linking
        (an employee who previously unlinked, or is switching Telegram
        accounts) is allowed and simply overwrites the previous values —
        there is no separate "already linked to yourself" error.
        """
        from apps.employees.domain.exceptions import EmployeeNotActiveError

        if self.status == EmployeeStatus.TERMINATED:
            raise EmployeeNotActiveError(
                f"Cannot link Telegram for a terminated employee ({self.employee_code})."
            )
        return Employee(
            id=self.id,
            employee_code=self.employee_code,
            user_id=self.user_id,
            profile=self.profile,
            contact_info=self.contact_info,
            employment_info=self.employment_info,
            status=self.status,
            telegram_user_id=telegram_user_id,
            telegram_chat_id=chat_id,
            telegram_username=telegram_username,
            telegram_linked_at=linked_at,
        )

    def unlink_telegram(self) -> "Employee":
        return Employee(
            id=self.id,
            employee_code=self.employee_code,
            user_id=self.user_id,
            profile=self.profile,
            contact_info=self.contact_info,
            employment_info=self.employment_info,
            status=self.status,
            telegram_user_id=None,
            telegram_chat_id=None,
            telegram_username=None,
            telegram_linked_at=None,
        )

    def activate(self) -> "Employee":
        """ACTIVE <- SUSPENDED/ON_LEAVE. Not valid from TERMINATED —
        termination is treated as a permanent, one-way transition in this
        phase; reinstating a terminated employee is a rehire (a new
        employee_code, a new record), not a status flip. See
        domain/exceptions.py:InvalidEmployeeStatusTransitionError.
        """
        from apps.employees.domain.exceptions import InvalidEmployeeStatusTransitionError

        if self.status == EmployeeStatus.TERMINATED:
            raise InvalidEmployeeStatusTransitionError(
                f"Cannot activate a terminated employee ({self.employee_code})."
            )
        return self._with_status(EmployeeStatus.ACTIVE)

    def deactivate(self) -> "Employee":
        """ACTIVE/ON_LEAVE -> SUSPENDED. A reversible, administrative hold —
        distinct from termination, which this phase does not model as an
        action on this entity (see activate()'s docstring)."""
        from apps.employees.domain.exceptions import InvalidEmployeeStatusTransitionError

        if self.status == EmployeeStatus.TERMINATED:
            raise InvalidEmployeeStatusTransitionError(
                f"Cannot deactivate a terminated employee ({self.employee_code})."
            )
        return self._with_status(EmployeeStatus.SUSPENDED)

    def _with_status(self, status: EmployeeStatus) -> "Employee":
        # Entity is a frozen-by-convention dataclass (kw_only, but not
        # frozen=True since repositories construct it via ordinary
        # `Employee(**kwargs)` on hydration) — status transitions still
        # follow the functional-update style used throughout Identity
        # (e.g. login_user.py constructing a new User) for consistency,
        # even though nothing here technically forbids in-place mutation.
        return Employee(
            id=self.id,
            employee_code=self.employee_code,
            user_id=self.user_id,
            profile=self.profile,
            contact_info=self.contact_info,
            employment_info=self.employment_info,
            status=status,
            telegram_user_id=self.telegram_user_id,
            telegram_chat_id=self.telegram_chat_id,
            telegram_username=self.telegram_username,
            telegram_linked_at=self.telegram_linked_at,
        )


@dataclass(kw_only=True)
class EmployeeLinkToken(Entity):
    """A single-use, time-limited OTP credential for linking an Employee to
    a Telegram account — the Employee-module equivalent of Identity's
    (password reset) `PasswordResetToken`, same discipline: `token` only
    ever holds a SHA-256 digest of the OTP, never the raw code (see
    application/services/employee_telegram_linking_service.py).

    Unlike the old (removed) `identity.TelegramLinkToken`, this also carries
    the Telegram identifiers supplied at "request" time
    (telegram_user_id/chat_id/telegram_username) — verification needs them
    to complete `Employee.link_telegram()`, and there is no
    already-existing TelegramAccount row to read them back from anymore
    (that concept no longer exists at all).
    """

    employee_id: uuid.UUID
    token: str
    telegram_user_id: int
    chat_id: int
    telegram_username: str | None
    expires_at: datetime
    used_at: datetime | None = None
    # Incremented on every wrong-OTP submission against this token (see
    # EmployeeTelegramLinkingService.verify_link and
    # MAX_OTP_ATTEMPTS/TooManyOTPAttemptsError). A brute-force guard: a
    # 6-digit OTP has 1,000,000 possibilities, so unlimited guesses within
    # the 10-minute validity window is a meaningfully weak secret. Locking
    # the token out after a small number of wrong tries — rather than
    # locking the *employee* out of linking entirely — means a mistyped
    # code doesn't cost the employee anything beyond running /link again
    # for a fresh code.
    attempt_count: int = 0

    def is_valid(self, *, now: datetime) -> bool:
        return self.used_at is None and now < self.expires_at
