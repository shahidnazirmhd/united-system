from django.urls import path

from apps.identity.interface.role_views import (
    PermissionListView,
    RoleDetailView,
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
    UserActivateView,
    UserDeactivateView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("me/", CurrentUserView.as_view(), name="auth-current-user"),
    path("password-reset/request/", RequestPasswordResetView.as_view(), name="auth-password-reset-request"),
    path("password-reset/confirm/", ConfirmPasswordResetView.as_view(), name="auth-password-reset-confirm"),
    # Phase 12 (User Management): list/create share one path (GET/POST),
    # matching RoleListCreateView's existing convention below.
    path("users/", UserListCreateView.as_view(), name="auth-user-list-create"),
    path("users/<uuid:user_id>/", UserDetailView.as_view(), name="auth-user-detail"),
    path("users/<uuid:user_id>/activate/", UserActivateView.as_view(), name="auth-user-activate"),
    path("users/<uuid:user_id>/deactivate/", UserDeactivateView.as_view(), name="auth-user-deactivate"),
    path("users/<uuid:user_id>/roles/", UserRoleAssignmentView.as_view(), name="auth-user-role-assign"),
    path(
        "users/<uuid:user_id>/roles/<uuid:role_id>/",
        UserRoleRevocationView.as_view(),
        name="auth-user-role-revoke",
    ),
    path("roles/", RoleListCreateView.as_view(), name="auth-role-list-create"),
    path("roles/<uuid:role_id>/", RoleDetailView.as_view(), name="auth-role-detail"),
    path("permissions/", PermissionListView.as_view(), name="auth-permission-list"),
    # telegram/link/request/, telegram/link/verify/, telegram/unlink/,
    # telegram/status/ (Phase 7) removed — see interface/views.py's note.
    # Equivalent routes now live under apps/employees/interface/urls.py.
]
