"""Role management and role-assignment endpoints.

All gated behind identity.view_roles / identity.manage_roles — see
migrations/0002_seed_system_roles.py + 0006_rename_admin_role_and_prune_system_roles.py
for which system role holds these by default ("Admin", the only role that
still ships seeded — see 0006's docstring). Every other role is created and
managed by an Admin through this same API (Role Management UI).
"""
from __future__ import annotations

import uuid

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.application.dtos import (
    AssignRoleRequest,
    CreateRoleRequest,
    DeleteRoleRequest,
    RevokeRoleRequest,
    UpdateRoleRequest,
)
from apps.identity.interface import dependencies
from apps.identity.interface.permissions import HasPermission
from apps.identity.interface.serializers import (
    AssignRoleSerializer,
    CreateRoleSerializer,
    PermissionSerializer,
    RoleSerializer,
    UpdateRoleSerializer,
)
from shared_kernel.api.response import success_response


class RoleListCreateView(APIView):
    """GET/POST /api/v1/auth/roles/"""

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasPermission("identity.manage_roles")]
        return [HasPermission("identity.view_roles")]

    @extend_schema(
        summary="List roles",
        responses={200: RoleSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        result = dependencies.build_list_roles_use_case().execute()
        return success_response(RoleSerializer(result, many=True).data)

    @extend_schema(
        summary="Create a role",
        description="Requires identity.manage_roles. permission_codes must reference existing "
        "Permission rows.",
        request=CreateRoleSerializer,
        responses={201: RoleSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = CreateRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_create_role_use_case().execute(
            CreateRoleRequest(
                name=serializer.validated_data["name"],
                description=serializer.validated_data["description"],
                permission_codes=frozenset(serializer.validated_data["permission_codes"]),
            )
        )
        return success_response(RoleSerializer(result).data, status_code=201)


class RoleDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/auth/roles/{id}/ (Role & Permission
    Management phase). PATCH is a full-replace update (see
    UpdateRoleSerializer's docstring); DELETE enforces
    CannotDeleteSystemRoleError/RoleInUseError — see DeleteRoleUseCase."""

    def get_permissions(self):
        if self.request.method == "GET":
            return [HasPermission("identity.view_roles")]
        return [HasPermission("identity.manage_roles")]

    @extend_schema(summary="Get a role by id", responses={200: RoleSerializer})
    def get(self, request: Request, role_id: uuid.UUID) -> Response:
        role = dependencies.build_get_role_by_id_use_case().execute(role_id)
        return success_response(RoleSerializer(role).data)

    @extend_schema(
        summary="Update a role",
        description="Requires identity.manage_roles. Full-replace: permission_codes must "
        "list every permission the role should end up holding.",
        request=UpdateRoleSerializer,
        responses={200: RoleSerializer},
    )
    def patch(self, request: Request, role_id: uuid.UUID) -> Response:
        serializer = UpdateRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_update_role_use_case().execute(
            UpdateRoleRequest(
                role_id=role_id,
                name=serializer.validated_data["name"],
                description=serializer.validated_data["description"],
                permission_codes=frozenset(serializer.validated_data["permission_codes"]),
            )
        )
        return success_response(RoleSerializer(result).data)

    @extend_schema(
        summary="Delete a role",
        description="Requires identity.manage_roles. Fails with 409 if the role is a system "
        "role or is still assigned to any user.",
        responses={200: OpenApiResponse(description="Role deleted.")},
    )
    def delete(self, request: Request, role_id: uuid.UUID) -> Response:
        dependencies.build_delete_role_use_case().execute(DeleteRoleRequest(role_id=role_id))
        return success_response({"detail": "Role deleted."})


class PermissionListView(APIView):
    """GET /api/v1/auth/permissions/ — the full permission catalogue,
    feeding the Role create/edit form's permission picker."""

    permission_classes = [HasPermission("identity.view_roles")]

    @extend_schema(summary="List permissions", responses={200: PermissionSerializer(many=True)})
    def get(self, request: Request) -> Response:
        result = dependencies.build_list_permissions_use_case().execute()
        return success_response(PermissionSerializer(result, many=True).data)


class UserRoleAssignmentView(APIView):
    """POST /api/v1/auth/users/{user_id}/roles/ — assigns a role to a user."""

    permission_classes = [HasPermission("identity.manage_roles")]

    @extend_schema(
        summary="Assign a role to a user",
        request=AssignRoleSerializer,
        responses={200: OpenApiResponse(description="Role assigned.")},
    )
    def post(self, request: Request, user_id: uuid.UUID) -> Response:
        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dependencies.build_assign_role_use_case().execute(
            AssignRoleRequest(
                user_id=user_id,
                role_id=serializer.validated_data["role_id"],
                assigned_by=request.user.user_id,
            )
        )
        return success_response({"detail": "Role assigned."})


class UserRoleRevocationView(APIView):
    """DELETE /api/v1/auth/users/{user_id}/roles/{role_id}/ — revokes a role from a user."""

    permission_classes = [HasPermission("identity.manage_roles")]

    @extend_schema(
        summary="Revoke a role from a user",
        responses={200: OpenApiResponse(description="Role revoked.")},
    )
    def delete(self, request: Request, user_id: uuid.UUID, role_id: uuid.UUID) -> Response:
        dependencies.build_revoke_role_use_case().execute(
            RevokeRoleRequest(user_id=user_id, role_id=role_id)
        )
        return success_response({"detail": "Role revoked."})
