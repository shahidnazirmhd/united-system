"""Throttle classes used across the API.

`AuthUserRateThrottle` is declared now even though no authentication
endpoints exist yet (Identity module, next phase) — it's the class those
endpoints will opt into once built, so the convention (stricter limits on
auth-adjacent endpoints) is established before it's needed rather than
invented under pressure later.
"""
from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class StandardUserRateThrottle(UserRateThrottle):
    scope = "standard"


class AuthUserRateThrottle(UserRateThrottle):
    scope = "auth"


class TelegramLinkRateThrottle(UserRateThrottle):
    """Scoped separately from `auth` — Telegram linking (Phase 7) is a
    second, independent entry point into obtaining a session, with its own
    abuse profile (OTP brute-forcing in particular), so it gets its own
    rate budget rather than sharing `auth`'s. `UserRateThrottle` falls back
    to IP-based limiting for unauthenticated callers (`get_ident`), which
    is exactly right here since `link/request/` and `link/verify/` are
    necessarily called before any JWT exists.
    """

    scope = "telegram"
