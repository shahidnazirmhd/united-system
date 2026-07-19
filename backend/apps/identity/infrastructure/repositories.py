"""Django ORM-backed implementations of the Identity repository interfaces.

Every method here translates between *Record (persistence, this file's
imports) and the plain domain entities in domain/entities.py — this
translation boundary is the only place in the whole module allowed to know
both representations exist.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from apps.identity.domain.entities import (
    PasswordResetToken,
    Permission,
    Role,
    User,
)
from apps.identity.domain.repositories import (
    PasswordResetTokenRepository,
    PermissionRepository,
    RoleRepository,
    UserRepository,
)
from apps.identity.domain.value_objects import Email
from apps.identity.infrastructure.models import (
    PasswordResetTokenRecord,
    PermissionRecord,
    RolePermissionRecord,
    RoleRecord,
    UserRecord,
    UserRoleRecord,
)


def _role_to_domain(role_record: RoleRecord) -> Role:
    return Role(
        id=role_record.id,
        name=role_record.name,
        description=role_record.description,
        is_system_role=role_record.is_system_role,
        permission_codes=frozenset(p.code for p in role_record.permissions.all()),
    )


def _user_to_domain(user_record: UserRecord) -> User:
    return User(
        id=user_record.id,
        email=Email(user_record.email),
        password_hash=user_record.password_hash,
        is_active=user_record.is_active,
        is_system_account=user_record.is_system_account,
        employee_id=user_record.employee_id,
        last_login_at=user_record.last_login_at,
        password_changed_at=user_record.password_changed_at,
        roles=tuple(_role_to_domain(r) for r in user_record.roles.all()),
    )


class DjangoUserRepository(UserRepository):
    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        record = (
            UserRecord.objects.prefetch_related("roles__permissions")
            .filter(id=user_id)
            .first()
        )
        return _user_to_domain(record) if record else None

    def get_by_email(self, email: Email) -> User | None:
        record = (
            UserRecord.objects.prefetch_related("roles__permissions")
            .filter(email=str(email))
            .first()
        )
        return _user_to_domain(record) if record else None

    def save(self, user: User) -> User:
        record, _ = UserRecord.objects.update_or_create(
            id=user.id,
            defaults={
                "email": str(user.email),
                "password_hash": user.password_hash,
                "is_active": user.is_active,
                "is_system_account": user.is_system_account,
                "employee_id": user.employee_id,
                "last_login_at": user.last_login_at,
                "password_changed_at": user.password_changed_at,
            },
        )
        record = UserRecord.objects.prefetch_related("roles__permissions").get(id=record.id)
        return _user_to_domain(record)

    def exists_with_email(self, email: Email) -> bool:
        return UserRecord.objects.filter(email=str(email)).exists()

    def assign_role(self, user_id: uuid.UUID, role_id: uuid.UUID, assigned_by: uuid.UUID | None) -> None:
        UserRoleRecord.objects.get_or_create(
            user_id=user_id, role_id=role_id, defaults={"assigned_by": assigned_by}
        )

    def revoke_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        UserRoleRecord.objects.filter(user_id=user_id, role_id=role_id).delete()

    def has_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        return UserRoleRecord.objects.filter(user_id=user_id, role_id=role_id).exists()


class DjangoRoleRepository(RoleRepository):
    def get_by_id(self, role_id: uuid.UUID) -> Role | None:
        record = RoleRecord.objects.prefetch_related("permissions").filter(id=role_id).first()
        return _role_to_domain(record) if record else None

    def get_by_name(self, name: str) -> Role | None:
        record = RoleRecord.objects.prefetch_related("permissions").filter(name=name).first()
        return _role_to_domain(record) if record else None

    def list_all(self) -> list[Role]:
        records = RoleRecord.objects.prefetch_related("permissions").all().order_by("name")
        return [_role_to_domain(r) for r in records]

    def save(self, role: Role, permission_codes: frozenset[str]) -> Role:
        record, _ = RoleRecord.objects.update_or_create(
            id=role.id,
            defaults={
                "name": role.name,
                "description": role.description,
                "is_system_role": role.is_system_role,
            },
        )
        if permission_codes:
            permission_records = PermissionRecord.objects.filter(code__in=permission_codes)
            RolePermissionRecord.objects.bulk_create(
                [
                    RolePermissionRecord(role=record, permission=p)
                    for p in permission_records
                ],
                ignore_conflicts=True,
            )
        record = RoleRecord.objects.prefetch_related("permissions").get(id=record.id)
        return _role_to_domain(record)

    def exists_with_name(self, name: str) -> bool:
        return RoleRecord.objects.filter(name=name).exists()


class DjangoPermissionRepository(PermissionRepository):
    def list_all(self) -> list[Permission]:
        return [
            Permission(id=p.id, code=p.code, description=p.description, module=p.module)
            for p in PermissionRecord.objects.all().order_by("module", "code")
        ]

    def get_by_codes(self, codes: frozenset[str]) -> list[Permission]:
        return [
            Permission(id=p.id, code=p.code, description=p.description, module=p.module)
            for p in PermissionRecord.objects.filter(code__in=codes)
        ]


class DjangoPasswordResetTokenRepository(PasswordResetTokenRepository):
    def create(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        record = PasswordResetTokenRecord.objects.create(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        return PasswordResetToken(
            id=record.id,
            user_id=record.user_id,
            token_hash=record.token_hash,
            expires_at=record.expires_at,
            used_at=record.used_at,
        )

    def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        record = PasswordResetTokenRecord.objects.filter(token_hash=token_hash).first()
        if record is None:
            return None
        return PasswordResetToken(
            id=record.id,
            user_id=record.user_id,
            token_hash=record.token_hash,
            expires_at=record.expires_at,
            used_at=record.used_at,
        )

    def mark_used(self, token_hash: str, *, used_at: datetime) -> None:
        PasswordResetTokenRecord.objects.filter(token_hash=token_hash).update(used_at=used_at)


# DjangoTelegramAccountRepository/DjangoTelegramLinkTokenRepository removed
# along with their tables — see infrastructure/models.py's module notes.
# Equivalent repository implementations now live in
# apps/employees/infrastructure/repositories.py.
