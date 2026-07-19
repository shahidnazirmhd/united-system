"""Shared Django ORM base classes.

These are infrastructure-layer concerns (persistence), not domain concerns.
A module's domain entities (plain Python, e.g.
apps/employees/domain/entities.py) never subclass these — only that same
module's infrastructure-layer ORM models do.

Phase 6 naming note: `TimestampedModel`/`AuditedModel` were renamed to
`TimestampModel`/`AuditModel` to match the names used project-wide going
forward. This is safe against the already-applied identity migrations —
Django migrations record concrete fields via `CreateModel`, never a
reference to the abstract class that produced them (see
apps/identity/migrations/0001_initial.py: it lists raw fields, not
"inherits from AuditedModel") — so renaming the Python class touches no
schema and required no new migration on identity.

`SoftDeleteModel` is new in Phase 6, and deliberately NOT folded into
`BaseModel`. If it were, every existing identity table would silently need
new columns via a retroactive migration the moment this file changed —
exactly the kind of "modifying an existing module to add a new module's
capability" the architecture forbids. Instead it's an opt-in mixin: a
module composes `class FooRecord(BaseModel, SoftDeleteModel):` when it
wants soft-delete semantics (see apps/employees/infrastructure/models.py),
leaving every module that doesn't need it, including identity today,
completely untouched.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from shared_kernel.infrastructure.uuid7 import generate_uuid7


class UUIDPrimaryKeyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)

    class Meta:
        abstract = True


class TimestampModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditModel(TimestampModel):
    """Adds who-changed-it tracking.

    `created_by`/`updated_by` are plain UUID columns, not ForeignKeys — per
    HRMS_Database_Design.md, cross-module references (including to
    identity.users) are never real database foreign keys; referential
    integrity for them is an application-layer concern, enforced through the
    port/adapter pattern rather than the database.
    """

    created_by = models.UUIDField(null=True, blank=True)
    updated_by = models.UUIDField(null=True, blank=True)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, AuditModel):
    """The base every future module's infrastructure-layer ORM models
    inherit from, unless a specific table has a documented reason not to
    (e.g. audit.audit_log, which intentionally uses a BIGINT identity key —
    see HRMS_Database_Design.md section 5.1)."""

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self) -> "SoftDeleteQuerySet":
        return self.filter(is_deleted=False)

    def dead(self) -> "SoftDeleteQuerySet":
        return self.filter(is_deleted=True)

    def delete(self):
        """Bulk soft-delete. Matches the instance-level `.delete()` override
        below — calling `.delete()` on a queryset from this manager never
        issues a `DELETE FROM ...` by accident."""
        return super().update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager):
    """The default manager on any `SoftDeleteModel` subclass — ordinary
    `Model.objects.filter(...)` calls never see soft-deleted rows. Declared
    first (see `SoftDeleteModel` below) so Django treats it as the model's
    default manager for internal use (e.g. `related_name` reverse access).

    Known limitation, not silently hidden: Django's FK `on_delete=CASCADE`
    still issues a real `DELETE` on related rows when the *parent* object is
    hard-deleted — soft-delete only intercepts `.delete()` calls made
    through this manager/queryset, it does not change what CASCADE means at
    the database level. Modules relying on soft-delete for a row that has
    CASCADE children should soft-delete children explicitly rather than
    relying on cascade to do it.
    """

    def get_queryset(self) -> SoftDeleteQuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_deleted=False)


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.UUIDField(null=True, blank=True)

    objects = SoftDeleteManager()
    # Escape hatch for admin/audit/repair code that must see everything,
    # including soft-deleted rows — never used by ordinary application code.
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, *, deleted_by=None):  # type: ignore[override]
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(using=using, update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def hard_delete(self, using=None, keep_parents=False) -> None:
        super().delete(using=using, keep_parents=keep_parents)
