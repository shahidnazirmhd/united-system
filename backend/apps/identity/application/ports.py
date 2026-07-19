"""Interfaces the Identity application layer depends on but does not
implement — Dependency Inversion applied to hashing, token issuance,
revocation, and email delivery. Concrete implementations live in
infrastructure/ (password_hasher.py, jwt_service.py, token_blocklist.py,
email_sender.py) and are swappable without touching any use case.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta


class PasswordHasherPort(ABC):
    @abstractmethod
    def hash(self, raw_password: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def verify(self, raw_password: str, password_hash: str) -> bool:
        raise NotImplementedError


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_expires_in_seconds: int


@dataclass(frozen=True)
class DecodedToken:
    user_id: uuid.UUID
    token_type: str  # "access" | "refresh"
    jti: str
    issued_at: datetime
    expires_at: datetime


class TokenServicePort(ABC):
    @abstractmethod
    def issue_pair(self, *, user_id: uuid.UUID, email: str) -> TokenPair:
        raise NotImplementedError

    @abstractmethod
    def decode(self, token: str) -> DecodedToken:
        """Raises InvalidTokenError (domain/exceptions.py) if the token is
        malformed, has an invalid signature, or is expired."""
        raise NotImplementedError


class TokenBlocklistPort(ABC):
    @abstractmethod
    def revoke(self, jti: str, *, ttl: timedelta) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_revoked(self, jti: str) -> bool:
        raise NotImplementedError


class EmailSenderPort(ABC):
    @abstractmethod
    def send_password_reset_email(self, *, to_email: str, raw_token: str) -> None:
        raise NotImplementedError


# EmployeeSummary/EmployeeLookupPort/OTPSenderPort (Phase 7's Telegram
# linking) removed — Identity no longer looks up Employee data at all, for
# any reason. Telegram linking is entirely an apps/employees concern now
# (see apps/employees/application/ports.py's EmployeeOTPEmailPort), so the
# cross-module port this file used to own has no reason to exist.
