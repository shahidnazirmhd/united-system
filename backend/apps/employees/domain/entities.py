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

from apps.employees.domain.enums import EmployeeCurrentStatus, EmployeeStatus
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
    # Round 14 item 8 — a second, HR-visible "day-to-day work status"
    # field, deliberately distinct from `status` above. See
    # `EmployeeCurrentStatus`'s own docstring (domain/enums.py) for the
    # full reasoning on why both fields coexist.
    current_status: EmployeeCurrentStatus = EmployeeCurrentStatus.NOT_JOINED
    # Set only while `current_status` is a system-managed leave status
    # (SICK_LEAVE/ANNUAL_LEAVE) — remembers what to revert to when the
    # leave ends (e.g. WORKING). None whenever current_status isn't one of
    # those two values.
    status_before_leave: EmployeeCurrentStatus | None = None

    @property
    def is_linked_to_telegram(self) -> bool:
        return self.telegram_user_id is not None

    @property
    def is_eligible_for_leave(self) -> bool:
        """Round 14 item 6 — an employee may not apply for leave while
        Not Joined, Terminated, or Resigned. "Currently on leave" (the
        fourth disallowed state from the brief) is deliberately NOT part of
        this check: it's enforced separately, against the specific dates
        being requested, by `LeaveValidationService.validate_no_overlap`
        (an employee can still apply for a *future* leave while currently
        on a *different, non-overlapping* approved leave)."""
        return self.current_status not in (
            EmployeeCurrentStatus.NOT_JOINED,
            EmployeeCurrentStatus.TERMINATED,
            EmployeeCurrentStatus.RESIGNED,
        )

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

        # Round 14 item 7 broadened this guard from "TERMINATED only" to
        # "must be ACTIVE or ON_LEAVE" — a SUSPENDED (deactivated) employee
        # must not be able to link Telegram either, matching the new
        # "prevent the employee from linking Telegram again while
        # inactive" requirement. ON_LEAVE remains allowed: that status
        # means the account is still active, just currently on leave.
        if self.status not in (EmployeeStatus.ACTIVE, EmployeeStatus.ON_LEAVE):
            raise EmployeeNotActiveError(
                "Your employee account is currently deactivated, so Telegram cannot be linked. "
                "Please contact HR to reactivate your account first."
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
            current_status=self.current_status,
            status_before_leave=self.status_before_leave,
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
            current_status=self.current_status,
            status_before_leave=self.status_before_leave,
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
            current_status=self.current_status,
            status_before_leave=self.status_before_leave,
        )

    # --- Current Status (round 14 item 8) --------------------------------

    def update_current_status_manually(self, new_status: EmployeeCurrentStatus) -> "Employee":
        """HR/Admin manual path (e.g. Not Joined -> Working). See
        `EmployeeCurrentStatus`'s docstring for the full transition rules;
        enforced here rather than left to the caller so no interface-layer
        code can ever bypass them (CODING_STANDARD.md: business rules live
        in the domain/application layers, never the view)."""
        from apps.employees.domain.exceptions import InvalidCurrentStatusTransitionError

        if self.current_status in (EmployeeCurrentStatus.TERMINATED, EmployeeCurrentStatus.RESIGNED):
            raise InvalidCurrentStatusTransitionError(
                f"Employee {self.employee_code}'s status is {self.current_status.value} — this is terminal."
            )
        if new_status in (EmployeeCurrentStatus.SICK_LEAVE, EmployeeCurrentStatus.ANNUAL_LEAVE):
            raise InvalidCurrentStatusTransitionError(
                "Sick Leave/Annual Leave are set automatically when a leave request is approved "
                "and cannot be chosen manually."
            )
        is_on_managed_leave = self.current_status in (
            EmployeeCurrentStatus.SICK_LEAVE,
            EmployeeCurrentStatus.ANNUAL_LEAVE,
        )
        if is_on_managed_leave and new_status not in (
            EmployeeCurrentStatus.TERMINATED,
            EmployeeCurrentStatus.RESIGNED,
        ):
            raise InvalidCurrentStatusTransitionError(
                f"Employee {self.employee_code} is currently on {self.current_status.value}; status is "
                "managed automatically until the leave ends. It can only be manually changed to "
                "Terminated or Resigned while on leave."
            )
        return self._with_current_status(new_status, status_before_leave=None)

    def enter_leave_status(self, leave_status: EmployeeCurrentStatus) -> "Employee":
        """System-only path — called by Leave's status integration
        (apps.leave, via its own EmployeeStatusPort) when an approved
        leave's period starts. Terminated/Resigned are never touched (round
        14 item 8: "Terminated and Resigned employees should not be
        automatically changed by leave processes")."""
        from apps.employees.domain.exceptions import InvalidCurrentStatusTransitionError

        if leave_status not in (EmployeeCurrentStatus.SICK_LEAVE, EmployeeCurrentStatus.ANNUAL_LEAVE):
            raise InvalidCurrentStatusTransitionError(
                f"{leave_status.value} is not a leave status Leave's integration may enter."
            )
        if self.current_status in (EmployeeCurrentStatus.TERMINATED, EmployeeCurrentStatus.RESIGNED):
            raise InvalidCurrentStatusTransitionError(
                f"Employee {self.employee_code}'s status is {self.current_status.value} — this is terminal "
                "and is never changed by leave processes."
            )
        # Already on a (possibly different) leave status — e.g. two
        # back-to-back approved leaves with no gap: preserve the ORIGINAL
        # status_before_leave rather than overwriting it with the first
        # leave's own leave status, so exit_leave_status() still reverts to
        # the real underlying employment status, not to the first leave.
        remembered = (
            self.status_before_leave
            if self.current_status in (EmployeeCurrentStatus.SICK_LEAVE, EmployeeCurrentStatus.ANNUAL_LEAVE)
            else self.current_status
        )
        return self._with_current_status(leave_status, status_before_leave=remembered)

    def exit_leave_status(self) -> "Employee":
        """System-only path — called when an approved leave's period ends.
        Reverts to whatever `status_before_leave` remembered (defaulting to
        WORKING if somehow unset — defensive only, `enter_leave_status`
        always sets it). No-op guard: raises if the employee isn't
        currently on a system-managed leave status at all (misuse by the
        caller, not a real state this method should silently swallow)."""
        from apps.employees.domain.exceptions import InvalidCurrentStatusTransitionError

        if self.current_status not in (EmployeeCurrentStatus.SICK_LEAVE, EmployeeCurrentStatus.ANNUAL_LEAVE):
            raise InvalidCurrentStatusTransitionError(
                f"Employee {self.employee_code} is not currently on a system-managed leave status."
            )
        reverted_to = self.status_before_leave or EmployeeCurrentStatus.WORKING
        return self._with_current_status(reverted_to, status_before_leave=None)

    def _with_current_status(
        self, current_status: EmployeeCurrentStatus, *, status_before_leave: EmployeeCurrentStatus | None
    ) -> "Employee":
        return Employee(
            id=self.id,
            employee_code=self.employee_code,
            user_id=self.user_id,
            profile=self.profile,
            contact_info=self.contact_info,
            employment_info=self.employment_info,
            status=self.status,
            telegram_user_id=self.telegram_user_id,
            telegram_chat_id=self.telegram_chat_id,
            telegram_username=self.telegram_username,
            telegram_linked_at=self.telegram_linked_at,
            current_status=current_status,
            status_before_leave=status_before_leave,
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
