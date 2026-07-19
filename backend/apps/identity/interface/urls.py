from django.urls import path

from apps.identity.interface.role_views import (
    RoleListCreateView,
    UserRoleAssignmentView,
    UserRoleRevocationView,
)
from apps.identity.interface.views import (
    ConfirmPasswordResetView,
    CurrentUserView,
    LoginView,
    LogoutView,
    RequestPasswordResetView,
    TokenRefreshView,
    UserCreateView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("me/", CurrentUserView.as_view(), name="auth-current-user"),
    path("password-reset/request/", RequestPasswordResetView.as_view(), name="auth-password-reset-request"),
    path("password-reset/confirm/", ConfirmPasswordResetView.as_view(), name="auth-password-reset-confirm"),
    path("users/", UserCreateView.as_view(), name="auth-user-create"),
    path("users/<uuid:user_id>/roles/", UserRoleAssignmentView.as_view(), name="auth-user-role-assign"),
    path(
        "users/<uuid:user_id>/roles/<uuid:role_id>/",
        UserRoleRevocationView.as_view(),
        name="auth-user-role-revoke",
    ),
    path("roles/", RoleListCreateView.as_view(), name="auth-role-list-create"),
    # telegram/link/request/, telegram/link/verify/, telegram/unlink/,
    # telegram/status/ (Phase 7) removed — see interface/views.py's note.
    # Equivalent routes now live under apps/employees/interface/urls.py.
]
