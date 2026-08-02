"""Django ORM models for Employees.

Named with a "Record" suffix, matching Identity's convention exactly (see
apps/identity/infrastructure/models.py's docstring for the full reasoning).
`EmployeeRecord` is intentionally one flat table — HRMS_Database_Design.md
section 3.2's already-approved `employees.employees` — even though the
domain `Employee` entity (domain/entities.py) is composed of nested value
objects; `infrastructure/repositories.py` is the only code that flattens/
nests between the two.

`EmployeeRecord` composes `BaseModel` with `SoftDeleteModel`
(shared_kernel/infrastructure/base_models.py) — an HR employee record is
exactly the kind of row that should never be truly gone from the database
(compliance, historical reporting), so soft-delete is the right default
here, opted into explicitly rather than inherited silently.

Table names are prefixed `employees_` rather than living in a real
PostgreSQL `employees` schema, for the same reason Identity's tables are
prefixed `identity_` — see that module's models.py docstring; the
reasoning is identical and not repeated module by module.
"""
from __future__ import annotations

from django.db import models

from apps.employees.domain.enums import EmployeeCurrentStatus, EmployeeStatus, EmploymentType
from shared_kernel.infrastructure.base_models import BaseModel, SoftDeleteModel


class DepartmentRecord(BaseModel):
    """Minimal supporting table — not a full module this phase (no REST API
    of its own), added only because `EmployeeRecord.department` is a real,
    same-schema foreign key HRMS_Database_Design.md already approved. See
    this phase's architecture notes for why this exists despite not being
    in the requested model list.
    """

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True)
    parent_department = models.ForeignKey(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="child_departments",
    )
    # FK to EmployeeRecord added via a later migration once that table
    # exists (the two tables are mutually referential) — see
    # migrations/0001_initial.py for the two-step CreateModel/AddField
    # sequence, matching HRMS_Database_Design.md's documented "circular
    # reference" resolution (section 3.2).
    head_employee = models.ForeignKey(
        "EmployeeRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_departments",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "employees_departments"

    def __str__(self) -> str:
        return self.name


class EmployeeRecord(BaseModel, SoftDeleteModel):
    employee_code = models.CharField(max_length=20, unique=True)
    # Logical reference to identity_users.id — plain UUID, never a
    # ForeignKey, per HRMS_Database_Design.md section 5 (no cross-module
    # foreign keys). Nullable and unique: the reciprocal of
    # identity.UserRecord.employee_id.
    user_id = models.UUIDField(null=True, blank=True, unique=True)

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    # Open text, not a constrained choice field — see domain/value_objects.py
    # EmployeeProfile's docstring.
    gender = models.CharField(max_length=30, null=True, blank=True)

    work_email = models.EmailField(max_length=255, unique=True)
    personal_email = models.EmailField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    date_of_joining = models.DateField()
    # Round 15 item 9 — renamed from `termination_date`; used for both
    # resignation and termination cases (see domain/value_objects.py
    # EmploymentInformation's docstring).
    last_working_date = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=20, choices=EmployeeStatus.choices(), default=EmployeeStatus.ACTIVE.value
    )
    employment_type = models.CharField(max_length=20, choices=EmploymentType.choices())

    department = models.ForeignKey(
        DepartmentRecord, on_delete=models.RESTRICT, related_name="employees"
    )
    manager = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="direct_reports"
    )
    job_title = models.CharField(max_length=150)

    # --- Telegram linking (Employee & Telegram Authentication refactor) --
    # The permanent link between this Employee and their Telegram account —
    # see domain/entities.py Employee's own docstring for the field-by-field
    # reasoning. Deliberately plain columns on this same table, not a
    # separate one-to-one table: exactly the same "always read/written
    # together as one row" argument value_objects.py already makes for
    # ContactInformation/EmploymentInformation applies here too.
    telegram_user_id = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_chat_id = models.BigIntegerField(null=True, blank=True)
    telegram_username = models.CharField(max_length=100, null=True, blank=True)
    telegram_linked_at = models.DateTimeField(null=True, blank=True)

    # --- Current Status (round 14 item 8) --------------------------------
    # Deliberately separate from `employment_status` above — see
    # domain/enums.py EmployeeCurrentStatus's docstring for the full
    # reasoning on why both fields exist.
    current_status = models.CharField(
        max_length=20, choices=EmployeeCurrentStatus.choices(), default=EmployeeCurrentStatus.NOT_JOINED.value
    )
    status_before_leave = models.CharField(
        max_length=20, choices=EmployeeCurrentStatus.choices(), null=True, blank=True
    )

    class Meta:
        db_table = "employees_employees"
        indexes = [
            models.Index(fields=["employment_status"], name="employees_status_idx"),
            models.Index(fields=["department"], name="employees_department_idx"),
            models.Index(fields=["telegram_user_id"], name="employees_telegram_tguid_idx"),
            models.Index(fields=["current_status"], name="employees_current_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(last_working_date__isnull=True)
                | models.Q(last_working_date__gte=models.F("date_of_joining")),
                name="employees_last_working_date_after_joining",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee_code} — {self.first_name} {self.last_name}"


class EmployeeLinkTokenRecord(BaseModel):
    """Employee & Telegram Authentication refactor — moved from (removed)
    identity.TelegramLinkTokenRecord, keyed by `employee` (FK to
    EmployeeRecord, same schema — a real FK, unlike the cross-module
    user_id/employee_id references elsewhere in this file) instead of a
    cross-module user reference. `token` stores a SHA-256 hex digest of the
    OTP, never the raw code — identical discipline to
    identity.PasswordResetTokenRecord.token_hash.

    Also carries the Telegram identifiers supplied at "request" time
    (telegram_user_id/chat_id/telegram_username): verification needs them
    to complete the link, and unlike the old TelegramAccountRecord this
    replaces, there is no separate not-yet-verified "pending account" row
    to read them back from.
    """

    employee = models.ForeignKey(EmployeeRecord, on_delete=models.CASCADE, related_name="link_tokens")
    token = models.CharField(max_length=64, unique=True)
    telegram_user_id = models.BigIntegerField()
    chat_id = models.BigIntegerField()
    telegram_username = models.CharField(max_length=100, null=True, blank=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    # Brute-force guard — see domain/entities.py EmployeeLinkToken.attempt_count
    # and application/services/employee_telegram_linking_service.py's
    # MAX_OTP_ATTEMPTS for the full reasoning.
    attempt_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "employees_link_tokens"
        indexes = [
            # get_pending_by_chat's lookup shape exactly — see
            # infrastructure/repositories.py.
            models.Index(fields=["telegram_user_id", "chat_id"], name="employees_link_tok_chat_idx"),
        ]

    def __str__(self) -> str:
        return f"link-token for employee:{self.employee_id}"
