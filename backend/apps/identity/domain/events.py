"""Domain events published by the Identity module.

Notification module (future) will subscribe to these once it exists — see
shared_kernel/infrastructure/event_bus_impl.py for why that subscription
doesn't need to exist yet for these events to be published now.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from shared_kernel.domain.domain_event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserLoggedIn(DomainEvent):
    user_id: uuid.UUID
    source: str = "web"  # "web" | "telegram" | "api" — see HRMS_Database_Design.md audit design


@dataclass(frozen=True, kw_only=True)
class UserLoggedOut(DomainEvent):
    user_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class RoleAssignedToUser(DomainEvent):
    user_id: uuid.UUID
    role_id: uuid.UUID
    assigned_by: uuid.UUID | None


@dataclass(frozen=True, kw_only=True)
class RoleRevokedFromUser(DomainEvent):
    user_id: uuid.UUID
    role_id: uuid.UUID
    revoked_by: uuid.UUID | None


@dataclass(frozen=True, kw_only=True)
class PasswordResetRequested(DomainEvent):
    """Published for audit/observability after the reset email has already
    been sent (RequestPasswordResetUseCase calls EmailSenderPort directly,
    synchronously — it does not rely on an event subscriber to deliver the
    email). Deliberately carries no token material: nothing secret should
    ever ride on the event bus, even an in-process one.
    """

    user_id: uuid.UUID


@dataclass(frozen=True, kw_only=True)
class PasswordChanged(DomainEvent):
    user_id: uuid.UUID


# Telegram-linking events (TelegramLinkRequested, TelegramAccountLinked,
# TelegramAccountUnlinked) moved to apps/employees/domain/events.py — see
# that module's docstring. Employees are linked to Telegram directly, never
# via an identity.User, so Identity no longer has a Telegram-linking
# concept of its own at all.
