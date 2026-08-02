"""Django ORM models for Identity.

Named with a "Record" suffix, deliberately distinct from the domain
entities in domain/entities.py (User, Role, Permission) — these classes
represent *how data is stored*, the domain entities represent *what the
data means*. The repository implementations below are the only code
allowed to translate between the two; nothing in application/ or domain/
ever imports from this file.

Table names are prefixed `identity_` rather than living in a real
PostgreSQL `identity` schema — see this phase's delivery notes for why:
implementing genuine multi-schema Postgres in Django requires either a
`db_table` quoting trick or careful `search_path` management, and neither
could be verified against a real database in the environment this was
built in. Module-boundary enforcement continues to rely on the
already-primary mechanism (no cross-module ORM imports, no cross-module
foreign keys) rather than the database schema itself.
"""
from __future__ import annotations

from django.db import models

from shared_kernel.infrastructure.base_models import BaseModel


class UserRecord(BaseModel):
    email = models.EmailField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=255)
    # Logical reference to a future employees.Employee row — plain UUID,
    # never a ForeignKey, per HRMS_Database_Design.md section 5 (no
    # cross-module foreign keys). Nullable and unique: not every user is an
    # employee, and an employee has at most one linked user account.
    employee_id = models.UUIDField(null=True, blank=True, unique=True)
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(auto_now_add=True)
    roles = models.ManyToManyField(
        "RoleRecord", through="UserRoleRecord", related_name="users", blank=True
    )

    class Meta:
        db_table = "identity_users"
        indexes = [
            models.Index(fields=["is_active"], name="identity_users_active_idx"),
        ]

    def __str__(self) -> str:
        return self.email


class RoleRecord(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")
    is_system_role = models.BooleanField(default=False)
    permissions = models.ManyToManyField(
        "PermissionRecord", through="RolePermissionRecord", related_name="roles", blank=True
    )

    class Meta:
        db_table = "identity_roles"

    def __str__(self) -> str:
        return self.name


class PermissionRecord(BaseModel):
    code = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")
    module = models.CharField(max_length=50, default="identity")

    class Meta:
        db_table = "identity_permissions"

    def __str__(self) -> str:
        return self.code


class UserRoleRecord(BaseModel):
    user = models.ForeignKey(UserRecord, on_delete=models.CASCADE, related_name="role_links")
    role = models.ForeignKey(RoleRecord, on_delete=models.CASCADE, related_name="user_links")
    # Logical reference to identity_users.id (the assigning admin) — plain
    # UUID rather than a self-referential FK, kept consistent with how every
    # other "who did this" column in this schema is modeled (see
    # created_by/updated_by on BaseModel).
    assigned_by = models.UUIDField(null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "identity_user_roles"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="unique_user_role"),
        ]


class RolePermissionRecord(BaseModel):
    role = models.ForeignKey(RoleRecord, on_delete=models.CASCADE, related_name="permission_links")
    permission = models.ForeignKey(
        PermissionRecord, on_delete=models.CASCADE, related_name="role_links"
    )

    class Meta:
        db_table = "identity_role_permissions"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="unique_role_permission"),
        ]


class PasswordResetTokenRecord(BaseModel):
    user = models.ForeignKey(
        UserRecord, on_delete=models.CASCADE, related_name="password_reset_tokens"
    )
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "identity_password_reset_tokens"


# TelegramAccountRecord/TelegramLinkTokenRecord (Phase 7) removed and their
# tables dropped — see migrations/0004_drop_telegram_tables.py. Employees are
# never issued a User account for Telegram, so Identity has nothing left to
# store about Telegram at all. The equivalent persistence now lives in
# apps/employees/infrastructure/models.py (EmployeeRecord's own telegram_*
# columns and the new EmployeeLinkTokenRecord), keyed by employee_id.
