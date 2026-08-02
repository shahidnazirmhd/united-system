"""Settings HTTP endpoints.

Plain `APIView`s, not `BaseViewSet` — this module's read/write shape
(a flat list of key-value rows, updated one key at a time) doesn't fit
`BaseViewSet`'s UUID-`pk`-keyed list/retrieve contract (see
domain/repositories.py's docstring). Every method still does exactly three
things — deserialize, call the service, serialize the result — per
CODING_STANDARD.md's "no business logic in views," matching every other
view in this codebase.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.settings.application.dtos import UpdateSettingRequest
from apps.settings.interface import dependencies
from apps.settings.interface.permissions import HasPermission, MANAGE_SETTINGS, VIEW_SETTINGS
from apps.settings.interface.serializers import SettingResponseSerializer, UpdateSettingSerializer
from shared_kernel.api.response import success_response


class SettingListView(APIView):
    permission_classes = [HasPermission(VIEW_SETTINGS)]

    @extend_schema(
        summary="List all application settings",
        description="Requires settings.view_settings.",
        responses={200: SettingResponseSerializer(many=True)},
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        results = dependencies.build_settings_service().list_settings()
        return success_response(SettingResponseSerializer(results, many=True).data)


class SettingDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "PATCH":
            return [HasPermission(MANAGE_SETTINGS)]
        return [HasPermission(VIEW_SETTINGS)]

    @extend_schema(
        summary="Get a single setting",
        description="Requires settings.view_settings.",
        responses={200: SettingResponseSerializer},
    )
    def get(self, request: Request, key: str, *args, **kwargs) -> Response:
        result = dependencies.build_settings_service().get_by_key(key)
        return success_response(SettingResponseSerializer(result).data)

    @extend_schema(
        summary="Update a setting's value",
        description="Requires settings.manage_settings. The key must already exist "
        "(seeded by a migration) — this endpoint never creates a new setting.",
        request=UpdateSettingSerializer,
        responses={200: SettingResponseSerializer},
    )
    def patch(self, request: Request, key: str, *args, **kwargs) -> Response:
        serializer = UpdateSettingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = dependencies.build_settings_service().update_setting(
            UpdateSettingRequest(
                key=key,
                value=serializer.validated_data["value"],
                updated_by=request.user.user_id,
            )
        )
        return success_response(SettingResponseSerializer(result).data)
