"""Telegram-linking endpoints — Gateway-facing only.

Every view here is called exclusively by the Telegram Gateway (a trusted
server-side client), never by an end user's browser or the Gateway's end
users directly — see TELEGRAM_GATEWAY.md's Authentication Flow. That is
why every one of these uses `HasInternalServiceKey`
(shared_kernel.api.permissions) instead of `IsAuthenticated`/`AllowAny`:
there is no employee JWT to check (employees are never issued one — see
this refactor's architecture notes), so what's being authorized is "is
this caller really the Gateway," not "which employee is this."

Distinct from EmployeeViewSet's `me` action (interface/viewsets.py), which
remains JWT-authenticated self-service for an HR System User who happens
to also have an Employee record linked via `user_id` — an orthogonal,
unaffected feature. These views are the Employee-module-owned replacement
for the endpoints Identity used to expose at /api/v1/auth/telegram/*
(removed — see apps/identity/interface/views.py's note).

Every method here does exactly three things — deserialize, call the
service, serialize the result — per CODING_STANDARD.md's "no business
logic in views," matching every other view in this codebase.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.application.dtos import RequestEmployeeTelegramLinkRequest, VerifyEmployeeTelegramLinkRequest
from apps.employees.interface import dependencies
from apps.employees.interface.serializers import (
    EmployeeResponseSerializer,
    EmployeeTelegramLinkStatusSerializer,
    RequestEmployeeTelegramLinkSerializer,
    TelegramUserIdQuerySerializer,
    VerifyEmployeeTelegramLinkSerializer,
)
from shared_kernel.api.permissions import HasInternalServiceKey
from shared_kernel.api.response import success_response
from shared_kernel.api.throttling import TelegramLinkRateThrottle

# Every view below sets authentication_classes = [] deliberately, not just
# permission_classes = [HasInternalServiceKey]. Leaving the default
# JWTAuthentication in place (from REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES)
# would still work in the sense that HasInternalServiceKey.has_permission()
# is what actually decides access — but DRF's own permission_denied() logic
# special-cases this: "if the view has any configured authenticators and
# none of them succeeded, raise NotAuthenticated (401) instead of
# PermissionDenied (403)". Since these callers never send a JWT (there is
# none to send — employees have no User account), JWTAuthentication always
# leaves request.successful_authenticator unset, which would silently
# downgrade every HasInternalServiceKey rejection to a misleading 401
# ("log in") instead of the correct 403 ("you're not allowed to call this
# at all"). Declaring no authenticators here removes that special case
# entirely, so a failed HasInternalServiceKey check reports 403, as its own
# tests (test_employee_telegram_endpoints.py) expect.
_NO_AUTHENTICATION: list = []


class RequestEmployeeTelegramLinkView(APIView):
    """POST /api/v1/employees/telegram/link/request/ — starts the linking
    flow: validates the employee code and dispatches a one-time OTP to every
    email the employee has on file — work_email always, plus personal_email
    too when set (real SMTP delivery or a log-only fallback — see
    shared_kernel.infrastructure.email_client). Always call 'verify' next
    with the OTP the employee enters into the bot; either copy of the OTP
    verifies successfully, since it's the identical code.
    """

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]
    throttle_classes = [TelegramLinkRateThrottle]

    @extend_schema(
        summary="Request a Telegram link (start registration)",
        request=RequestEmployeeTelegramLinkSerializer,
        responses={200: OpenApiResponse(description="OTP dispatched to the employee's registered email.")},
    )
    def post(self, request: Request) -> Response:
        serializer = RequestEmployeeTelegramLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dependencies.build_employee_telegram_linking_service().request_link(
            RequestEmployeeTelegramLinkRequest(
                employee_code=serializer.validated_data["employee_code"],
                telegram_user_id=serializer.validated_data["telegram_user_id"],
                chat_id=serializer.validated_data["chat_id"],
                telegram_username=serializer.validated_data["telegram_username"],
            )
        )
        return success_response({"detail": "OTP dispatched to the employee's registered email(s)."})


class VerifyEmployeeTelegramLinkView(APIView):
    """POST /api/v1/employees/telegram/link/verify/ — completes linking.

    Stores the Telegram user id directly on the Employee record (see
    domain/entities.py Employee.link_telegram) and returns the now-linked
    profile. No token pair is returned — there is nothing to authenticate
    with going forward except the Telegram user id itself.
    """

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]
    throttle_classes = [TelegramLinkRateThrottle]

    @extend_schema(
        summary="Verify a Telegram link OTP (complete registration)",
        request=VerifyEmployeeTelegramLinkSerializer,
        responses={200: EmployeeResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = VerifyEmployeeTelegramLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_employee_telegram_linking_service().verify_link(
            VerifyEmployeeTelegramLinkRequest(
                telegram_user_id=serializer.validated_data["telegram_user_id"],
                chat_id=serializer.validated_data["chat_id"],
                otp=serializer.validated_data["otp"],
                telegram_username=serializer.validated_data["telegram_username"],
            )
        )
        return success_response(EmployeeResponseSerializer(result).data)


class EmployeeUnlinkTelegramView(APIView):
    """POST /api/v1/employees/telegram/unlink/ — unlinks a Telegram account
    from whichever employee currently holds it."""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="Unlink a Telegram account",
        request=TelegramUserIdQuerySerializer,
        responses={200: OpenApiResponse(description="Unlinked.")},
    )
    def post(self, request: Request) -> Response:
        serializer = TelegramUserIdQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dependencies.build_employee_telegram_linking_service().unlink(
            serializer.validated_data["telegram_user_id"]
        )
        return success_response({"detail": "Telegram account unlinked."})


class EmployeeTelegramLinkStatusView(APIView):
    """GET /api/v1/employees/telegram/status/?telegram_user_id=... — is
    this Telegram account currently linked to an employee?"""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="Get Telegram link status",
        parameters=[TelegramUserIdQuerySerializer],
        responses={200: EmployeeTelegramLinkStatusSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = TelegramUserIdQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_employee_telegram_linking_service().get_link_status(
            serializer.validated_data["telegram_user_id"]
        )
        return success_response(EmployeeTelegramLinkStatusSerializer(result).data)


class EmployeeTelegramProfileView(APIView):
    """GET /api/v1/employees/telegram/profile/?telegram_user_id=... — the
    endpoint every post-linking Telegram request resolves through ("My
    Profile", "Employment Status" — both bot commands read different
    fields off this same response; see EMPLOYEE_API.md). Replaces the old
    JWT-authenticated `/employees/me/` for Gateway callers specifically —
    see this module's docstring for why `/employees/me/` itself is
    untouched, not repurposed.
    """

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="Get an employee's profile by Telegram user id",
        description="404 employee_not_linked_to_telegram if no employee currently has this "
        "Telegram user id linked.",
        parameters=[TelegramUserIdQuerySerializer],
        responses={200: EmployeeResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = TelegramUserIdQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_employee_service().get_profile_by_telegram_user_id(
            serializer.validated_data["telegram_user_id"]
        )
        return success_response(EmployeeResponseSerializer(result).data)
