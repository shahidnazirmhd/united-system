"""Holiday Management HTTP endpoints.

Extends shared_kernel's `BaseViewSet`, matching
`apps.employees.interface.viewsets.DepartmentViewSet`'s exact shape — no
delete action, same "deactivate (is_active=False via update), don't
hard-delete" precedent, since a past holiday is meaningful history for any
already-computed working-day calculation that referenced it.
"""
from __future__ import annotations

import uuid

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response

from apps.attendance.application.dtos import CreateHolidayRequest, UpdateHolidayRequest
from apps.attendance.application.services.holiday_service import HolidayService
from apps.attendance.infrastructure.models import HolidayRecord
from apps.attendance.interface import dependencies
from apps.attendance.interface.permissions import HasPermission, MANAGE_HOLIDAYS, VIEW_ATTENDANCE
from apps.attendance.interface.serializers import (
    CreateHolidaySerializer,
    HolidayResponseSerializer,
    UpdateHolidaySerializer,
)
from shared_kernel.api.base_viewset import BaseViewSet
from shared_kernel.api.response import success_response


class HolidayViewSet(BaseViewSet):
    queryset = HolidayRecord.objects.all()
    response_serializer_class = HolidayResponseSerializer
    filter_fields = ("is_active", "year")
    search_fields = ("name",)
    default_ordering = ("holiday_date",)

    def get_service(self) -> HolidayService:
        return dependencies.build_holiday_service()

    def get_permissions(self):
        if self.action in ("create", "update"):
            return [HasPermission(MANAGE_HOLIDAYS)]
        return [HasPermission(VIEW_ATTENDANCE)]

    @extend_schema(
        summary="Create a holiday",
        description="Requires attendance.manage_holidays.",
        request=CreateHolidaySerializer,
        responses={201: HolidayResponseSerializer},
    )
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = CreateHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = self.get_service().create_holiday(
            CreateHolidayRequest(
                name=data["name"],
                holiday_date=data["holiday_date"],
                description=data["description"],
                created_by=request.user.user_id,
            )
        )
        return success_response(HolidayResponseSerializer(result).data, status_code=201)

    @extend_schema(
        summary="Update a holiday",
        description="Full-replace update. Requires attendance.manage_holidays.",
        request=UpdateHolidaySerializer,
        responses={200: HolidayResponseSerializer},
    )
    def update(self, request: Request, pk: uuid.UUID | None = None, *args, **kwargs) -> Response:
        serializer = UpdateHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = self.get_service().update_holiday(
            UpdateHolidayRequest(
                holiday_id=pk,
                name=data["name"],
                holiday_date=data["holiday_date"],
                description=data["description"],
                is_active=data["is_active"],
                updated_by=request.user.user_id,
            )
        )
        return success_response(HolidayResponseSerializer(result).data)
