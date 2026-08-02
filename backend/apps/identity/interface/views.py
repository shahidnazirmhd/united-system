"""Authentication session endpoints: login, logout, token refresh, current
user, password reset, and (admin-gated) user creation.

Every view here does exactly three things — deserialize, call a use case,
serialize the result — per CODING_STANDARD.md's "no business logic in
views." Role management endpoints live in role_views.py.
"""
from __future__ import annotations

import uuid

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
    UpdateUserRequest,
    UserListQuery,
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
    UpdateUserSerializer,
    UserSummarySerializer,
)
from shared_kernel.api.query_params import parse_list_query_params
from shared_kernel.api.response import paginated_response, success_response


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


class UserListCreateView(APIView):
    """GET /api/v1/auth/users/ — lists users (Phase 12, User Management).
    POST /api/v1/auth/users/ — provisions a new authentication account.

    Admin-only (identity.manage_users for create, identity.view_users for
    list) — creation is not public self-service signup. See this module's
    architecture notes on why User and Employee are provisioned
    independently.
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasPermission("identity.manage_users")]
        return [HasPermission("identity.view_users")]

    @extend_schema(
        summary="List users",
        description="Requires identity.view_users. Query params: is_active "
        "(exact-match filter), search/q (matches email), ordering, page, page_size.",
        responses={200: UserSummarySerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = parse_list_query_params(
            request,
            filter_fields=("is_active",),
            search_fields=("email",),
            default_ordering=("email",),
        )

        def _as_bool(value: object) -> bool | None:
            if value is None:
                return None
            return str(value).lower() in ("1", "true", "yes")

        page_result = dependencies.build_list_users_use_case().execute(
            UserListQuery(
                is_active=_as_bool(query.filters.get("is_active")),
                search=query.search,
                ordering=query.ordering,
                page=query.page,
                page_size=query.page_size,
            )
        )
        return paginated_response(page_result, UserSummarySerializer(page_result.items, many=True).data)

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
                created_by=request.user.user_id,
            )
        )
        return success_response(UserSummarySerializer(result).data, status_code=201)


class UserDetailView(APIView):
    """GET /api/v1/auth/users/{user_id}/ — any user's profile (admin-gated,
    unlike GET /api/v1/auth/me/ which needs no permission at all).
    PATCH /api/v1/auth/users/{user_id}/ — edits email.
    """

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [HasPermission("identity.manage_users")]
        return [HasPermission("identity.view_users")]

    @extend_schema(
        summary="Get a user by id",
        description="Requires identity.view_users.",
        responses={200: UserSummarySerializer},
    )
    def get(self, request: Request, user_id: uuid.UUID) -> Response:
        result = dependencies.build_get_user_by_id_use_case().execute(user_id)
        return success_response(UserSummarySerializer(result).data)

    @extend_schema(
        summary="Edit a user",
        description="Full-replace update of email. Requires "
        "identity.manage_users. Does not change password (see password-reset "
        "endpoints) or roles (see the role-assignment endpoints) or is_active "
        "(see activate/deactivate).",
        request=UpdateUserSerializer,
        responses={200: UserSummarySerializer},
    )
    def patch(self, request: Request, user_id: uuid.UUID) -> Response:
        serializer = UpdateUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_update_user_use_case().execute(
            UpdateUserRequest(
                user_id=user_id,
                email=serializer.validated_data["email"],
                updated_by=request.user.user_id,
            )
        )
        return success_response(UserSummarySerializer(result).data)


class UserActivateView(APIView):
    """POST /api/v1/auth/users/{user_id}/activate/ — requires identity.manage_users."""

    permission_classes = [HasPermission("identity.manage_users")]

    @extend_schema(
        summary="Activate a user",
        request=None,
        responses={200: UserSummarySerializer},
    )
    def post(self, request: Request, user_id: uuid.UUID) -> Response:
        result = dependencies.build_activate_user_use_case().execute(user_id)
        return success_response(UserSummarySerializer(result).data)


class UserDeactivateView(APIView):
    """POST /api/v1/auth/users/{user_id}/deactivate/ — requires identity.manage_users.

    Takes effect immediately: is_active is checked fresh on every
    authenticated request (see this module's architecture notes), so a
    deactivated user's existing access/refresh tokens stop working on their
    very next request, with no separate revocation step needed.
    """

    permission_classes = [HasPermission("identity.manage_users")]

    @extend_schema(
        summary="Deactivate a user",
        request=None,
        responses={200: UserSummarySerializer},
    )
    def post(self, request: Request, user_id: uuid.UUID) -> Response:
        result = dependencies.build_deactivate_user_use_case().execute(user_id)
        return success_response(UserSummarySerializer(result).data)


# RequestTelegramLinkView/VerifyTelegramLinkView/UnlinkTelegramView/
# TelegramLinkStatusView (Phase 7) removed — Telegram-linked employees never
# obtain an Identity User or a JWT, so there is no Identity-owned endpoint
# for this anymore. The equivalent flow now lives in
# apps/employees/interface/views.py, authenticated by the Telegram Gateway's
# internal service key (shared_kernel.api.permissions.HasInternalServiceKey),
# not a bearer token. See TELEGRAM_GATEWAY.md for the current flow.
