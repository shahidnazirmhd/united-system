"""RBAC permission classes.

DRF's own `IsAuthenticated`/`AllowAny` (rest_framework.permissions) are
reused as-is for the "is there a caller at all" check — no need to
reinvent them, and they already work correctly against our
AuthenticatedPrincipal (shared_kernel/api/principal.py) since its
`is_authenticated` property satisfies what IsAuthenticated checks.
HasRole/HasPermission below are what this module actually adds, and are
meant to be imported by every future module's own interface/permissions.py
and composed with module-specific object-level rules — see
HRMS_Folder_Structure.md section 1.2 (identity/interface/permissions.py is
the one place other modules are expected to import from).
"""
from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class HasRole(BasePermission):
    """Usage: `permission_classes = [HasRole("Admin")]` — instantiate
    with the required role name. Multiple required roles can be composed
    with DRF's `|`/`&` permission operators, e.g. `HasRole("Admin") |
    HasRole("Auditor")`. In practice, every view in this codebase prefers
    `HasPermission` over `HasRole` — gating on a permission code rather than
    a specific role name is what lets an Admin freely rename/replace roles
    (Role Management, Phase "Role & Permission Management") without any
    view's authorization logic needing to change.
    """

    def __init__(self, role_name: str) -> None:
        self.role_name = role_name

    def __call__(self) -> "HasRole":
        # DRF instantiates permission_classes entries with no arguments
        # (`cls()`); returning self here lets a pre-built instance be used
        # directly in a `permission_classes` list despite DRF's calling
        # convention expecting a zero-arg class.
        return self

    def has_permission(self, request: Request, view: APIView) -> bool:
        principal = request.user
        return bool(principal and principal.is_authenticated and principal.has_role(self.role_name))


class HasPermission(BasePermission):
    """Usage: `permission_classes = [HasPermission("identity.manage_roles")]`."""

    def __init__(self, permission_code: str) -> None:
        self.permission_code = permission_code

    def __call__(self) -> "HasPermission":
        return self

    def has_permission(self, request: Request, view: APIView) -> bool:
        principal = request.user
        return bool(
            principal
            and principal.is_authenticated
            and principal.has_permission(self.permission_code)
        )
