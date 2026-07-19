"""Authentication session endpoints: login, logout, token refresh, current
user, password reset, and (admin-gated) user creation.

Every view here does exactly three things — deserialize, call a use case,
serialize the result — per CODING_STANDARD.md's "no business logic in
views." Role management endpoints live in role_views.py.
"""
from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.application.dtos import (
    ConfirmPasswordResetRequest,
    CreateUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RequestPasswordResetRequest,
)
from apps.identity.interface import dependencies
from apps.identity.interface.permissions import HasPermission
from apps.identity.interface.serializers import (
    ConfirmPasswordResetSerializer,
    CreateUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
    RequestPasswordResetSerializer,
    TokenPairResponseSerializer,
    UserSummarySerializer,
)
from shared_kernel.api.response import success_response


class LoginView(APIView):
    """POST /api/v1/auth/login/ — exchanges email+password for a token pair."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Log in",
        description="Authenticates with email and password, returns an access/refresh token pair.",
        request=LoginSerializer,
        responses={200: TokenPairResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_login_use_case().execute(
            LoginRequest(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
                source="web",
            )
        )
        return success_response(TokenPairResponseSerializer(result).data)


class LogoutView(APIView):
    """POST /api/v1/auth/logout/ — revokes the current session's tokens."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Log out",
        description="Revokes the presented refresh token and the current access token.",
        request=LogoutSerializer,
        responses={200: OpenApiResponse(description="Logged out successfully.")},
    )
    def post(self, request: Request) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access_token_jti = request.auth if isinstance(request.auth, str) else None
        dependencies.build_logout_use_case().execute(
            LogoutRequest(
                refresh_token=serializer.validated_data["refresh_token"],
                access_token_jti=access_token_jti,
            )
        )
        return success_response({"detail": "Logged out."})


class TokenRefreshView(APIView):
    """POST /api/v1/auth/token/refresh/ — rotates a refresh token for a new pair."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Refresh access token",
        description="Exchanges a valid, unrevoked refresh token for a new access/refresh pair. "
        "The presented refresh token is revoked as part of rotation.",
        request=RefreshSerializer,
        responses={200: TokenPairResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_refresh_use_case().execute(
            RefreshRequest(refresh_token=serializer.validated_data["refresh_token"])
        )
        return success_response(TokenPairResponseSerializer(result).data)


class CurrentUserView(APIView):
    """GET /api/v1/auth/me/ — the authenticated caller's own profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user",
        description="Returns the authenticated caller's profile, roles, and effective permissions.",
        responses={200: UserSummarySerializer},
    )
    def get(self, request: Request) -> Response:
        result = dependencies.build_get_current_user_use_case().execute(request.user.user_id)
        return success_response(UserSummarySerializer(result).data)


class RequestPasswordResetView(APIView):
    """POST /api/v1/auth/password-reset/request/ — starts a password reset.

    Always responds 200 regardless of whether the email exists — see
    RequestPasswordResetUseCase for why.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Request password reset",
        description="Always returns 200 whether or not the email is registered, to avoid "
        "leaking which addresses have accounts.",
        request=RequestPasswordResetSerializer,
        responses={200: OpenApiResponse(description="If that email exists, a reset link was sent.")},
    )
    def post(self, request: Request) -> Response:
        serializer = RequestPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dependencies.build_request_password_reset_use_case().execute(
            RequestPasswordResetRequest(email=serializer.validated_data["email"])
        )
        return success_response({"detail": "If that email exists, a reset link was sent."})


class ConfirmPasswordResetView(APIView):
    """POST /api/v1/auth/password-reset/confirm/ — completes a password reset."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Confirm password reset",
        description="Sets a new password using a valid, unexpired, unused reset token. "
        "Invalidates every existing session.",
        request=ConfirmPasswordResetSerializer,
        responses={200: OpenApiResponse(description="Password changed successfully.")},
    )
    def post(self, request: Request) -> Response:
        serializer = ConfirmPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dependencies.build_confirm_password_reset_use_case().execute(
            ConfirmPasswordResetRequest(
                token=serializer.validated_data["token"],
                new_password=serializer.validated_data["new_password"],
            )
        )
        return success_response({"detail": "Password changed successfully."})


class UserCreateView(APIView):
    """POST /api/v1/auth/users/ — provisions a new authentication account.

    Admin-only (identity.manage_users) — not public self-service signup.
    See this module's architecture notes on why User accounts are
    provisioned independently of the (not-yet-built) Employee module.
    """

    permission_classes = [HasPermission("identity.manage_users")]

    @extend_schema(
        summary="Create a user account",
        description="Creates a new authentication account. Requires identity.manage_users.",
        request=CreateUserSerializer,
        responses={201: UserSummarySerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = CreateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_create_user_use_case().execute(
            CreateUserRequest(
                email=serializer.validated_data["email"],
                password=serializer.validated_data["password"],
                is_system_account=serializer.validated_data["is_system_account"],
                created_by=request.user.user_id,
            )
        )
        return success_response(UserSummarySerializer(result).data, status_code=201)


# RequestTelegramLinkView/VerifyTelegramLinkView/UnlinkTelegramView/
# TelegramLinkStatusView (Phase 7) removed — Telegram-linked employees never
# obtain an Identity User or a JWT, so there is no Identity-owned endpoint
# for this anymore. The equivalent flow now lives in
# apps/employees/interface/views.py, authenticated by the Telegram Gateway's
# internal service key (shared_kernel.api.permissions.HasInternalServiceKey),
# not a bearer token. See TELEGRAM_GATEWAY.md for the current flow.
