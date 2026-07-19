"""Service-to-service authorization — distinct from apps.identity's
HasRole/HasPermission (apps/identity/interface/permissions.py), which
authorize a *human* caller holding a JWT.

HasInternalServiceKey authorizes a *trusted internal service* instead: the
Telegram Gateway, calling the backend's employee-lookup/OTP endpoints on
behalf of an employee who has no JWT of their own (Employee & Telegram
Authentication refactor — employees are never issued an identity.User or a
token). There is no per-employee principal to check a role/permission
against at this boundary, only "is this caller the Gateway, or an
impostor." A static shared secret, checked in constant time, is the
correct minimum viable control for that question — see this refactor's
architecture notes for why a full OAuth2 client-credentials flow would be
over-engineering for a single, fixed, first-party caller.

Lives in shared_kernel (not apps.identity) for the same reason
AuthenticatedPrincipal does: any module may need to expose a
Gateway-facing endpoint (today: apps.employees; potentially others later),
and none of them should depend on apps.identity's internals to do it.
"""
from __future__ import annotations

import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

INTERNAL_SERVICE_KEY_HEADER = "X-Internal-Service-Key"


class HasInternalServiceKey(BasePermission):
    """Usage: `permission_classes = [HasInternalServiceKey]`.

    Requires the request to carry a `X-Internal-Service-Key` header whose
    value matches `settings.INTERNAL_SERVICE_API_KEY` exactly, compared in
    constant time (`hmac.compare_digest`) to avoid leaking the correct
    value one byte at a time via response-timing side channels — the same
    discipline used for token hashes elsewhere in this codebase (see
    PasswordResetTokenRecord.token_hash lookups).

    Deliberately fails closed: if `INTERNAL_SERVICE_API_KEY` is unset or
    empty (e.g. a misconfigured environment), no header value — including
    an empty one — is treated as a match.
    """

    message = "A valid internal service key is required to access this endpoint."

    def has_permission(self, request: Request, view: APIView) -> bool:
        expected = getattr(settings, "INTERNAL_SERVICE_API_KEY", "") or ""
        if not expected:
            return False
        provided = request.headers.get(INTERNAL_SERVICE_KEY_HEADER, "")
        if not provided:
            return False
        return hmac.compare_digest(provided, expected)
