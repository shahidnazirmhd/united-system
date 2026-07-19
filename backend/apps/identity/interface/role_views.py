"""Role management and role-assignment endpoints.

All gated behind identity.view_roles / identity.manage_roles — see
infrastructure/migrations/0002_seed_system_roles.py for which system role
holds these by default (HR Admin).
"""
from __future__ import annotations

import uuid

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.application.dtos import AssignRoleRequest, CreateRoleRequest, RevokeRoleRequest
from apps.identity.interface import dependencies
from apps.identity.interface.permissions import HasPermission
from apps.identity.interface.serializers import (
    AssignRoleSerializer,
    CreateRoleSerializer,
    RoleSerializer,
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
