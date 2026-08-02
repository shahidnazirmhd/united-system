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
from django.db.models import Q
from shared_kernel.domain.repository import PageResult, QueryParams


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

    def get_by_employee_id(self, employee_id: uuid.UUID) -> User | None:
        record = (
            UserRecord.objects.prefetch_related("roles__permissions")
            .filter(employee_id=employee_id)
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

    def list(self, query: QueryParams) -> PageResult[User]:
        # Hand-written rather than delegating to DjangoBaseRepository (which
        # Identity's repositories don't extend — see this class's module
        # docstring): the logic is identical to that generic implementation,
        # just with the same `prefetch_related` every other read method here
        # already needs so `_user_to_domain` doesn't N+1 on roles/permissions.
        queryset = UserRecord.objects.prefetch_related("roles__permissions").all()

        if query.filters:
            queryset = queryset.filter(**query.filters)

        if query.search and query.search_fields:
            search_condition = Q()
            for field_name in query.search_fields:
                search_condition |= Q(**{f"{field_name}__icontains": query.search})
            queryset = queryset.filter(search_condition)

        total_count = queryset.count()

        if query.ordering:
            queryset = queryset.order_by(*query.ordering)

        start = (query.page - 1) * query.page_size
        end = start + query.page_size
        items = [_user_to_domain(record) for record in queryset[start:end]]

        return PageResult(items=items, total_count=total_count, page=query.page, page_size=query.page_size)

    def save(self, user: User) -> User:
        record, _ = UserRecord.objects.update_or_create(
            id=user.id,
            defaults={
                "email": str(user.email),
                "password_hash": user.password_hash,
                "is_active": user.is_active,
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

    def update(self, role: Role, permission_codes: frozenset[str]) -> Role:
        record, _ = RoleRecord.objects.update_or_create(
            id=role.id,
            defaults={"name": role.name, "description": role.description},
        )
        # Full replace, not additive like save(): clear every existing grant
        # first, then re-add exactly the target set — see RoleRepository.update's
        # docstring on why this differs from save()'s bulk_create-only approach.
        RolePermissionRecord.objects.filter(role=record).delete()
        if permission_codes:
            permission_records = PermissionRecord.objects.filter(code__in=permission_codes)
            RolePermissionRecord.objects.bulk_create(
                [RolePermissionRecord(role=record, permission=p) for p in permission_records]
            )
        record = RoleRecord.objects.prefetch_related("permissions").get(id=record.id)
        return _role_to_domain(record)

    def delete(self, role_id: uuid.UUID) -> None:
        RoleRecord.objects.filter(id=role_id).delete()

    def is_assigned_to_any_user(self, role_id: uuid.UUID) -> bool:
        return UserRoleRecord.objects.filter(role_id=role_id).exists()

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
