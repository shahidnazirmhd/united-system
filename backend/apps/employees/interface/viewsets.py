"""Employee HTTP endpoints.

Extends shared_kernel's `BaseViewSet` (list/retrieve inherited — see that
file's docstring for why those two are generalized and create/update
aren't). Every method here does exactly three things — deserialize, call
the service, serialize the result — matching CODING_STANDARD.md's "no
business logic in views," the same discipline Identity's views.py follows.
"""
from __future__ import annotations

import uuid

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.employees.application.dtos import CreateEmployeeRequest, UpdateEmployeeRequest
from apps.employees.application.services.employee_service import EmployeeService
from apps.employees.infrastructure.models import EmployeeRecord
from apps.employees.interface import dependencies
from apps.employees.interface.permissions import HasPermission, MANAGE_EMPLOYEES, VIEW_EMPLOYEES
from apps.employees.interface.serializers import (
    CreateEmployeeSerializer,
    EmployeeResponseSerializer,
    UpdateEmployeeSerializer,
)
from shared_kernel.api.base_viewset import BaseViewSet
from shared_kernel.api.response import success_response


class EmployeeViewSet(BaseViewSet):
    # Used by drf-spectacular for schema introspection only — list/retrieve
    # below go through EmployeeService, never this queryset directly.
    queryset = EmployeeRecord.objects.all()
    response_serializer_class = EmployeeResponseSerializer
    filter_fields = ("department_id", "employment_status", "employment_type")
    default_ordering = ("employee_code",)

    def get_service(self) -> EmployeeService:
        return dependencies.build_employee_service()

    def get_permissions(self):
        if self.action in ("create", "update", "activate", "deactivate"):
            return [HasPermission(MANAGE_EMPLOYEES)]
        if self.action == "me":
            # Self-service (Phase 7): viewing your OWN record needs only
            # authentication, not employees.view_employees — that
            # permission gates viewing *anyone's* record (HR Admin/Manager
            # territory), which is a strictly bigger grant than "see your
            # own profile," the thing Telegram self-service actually needs.
            return [IsAuthenticated()]
        return [HasPermission(VIEW_EMPLOYEES)]

    @extend_schema(
        summary="Create an employee",
        description="Creates a new employee record. Requires employees.manage_employees.",
        request=CreateEmployeeSerializer,
        responses={201: EmployeeResponseSerializer},
    )
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = CreateEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = self.get_service().create_employee(
            CreateEmployeeRequest(
                first_name=data["first_name"],
                last_name=data["last_name"],
                date_of_birth=data["date_of_birth"],
                gender=data["gender"],
                work_email=data["work_email"],
                personal_email=data["personal_email"],
                phone_number=data["phone_number"],
                department_id=data["department_id"],
                manager_id=data["manager_id"],
                job_title=data["job_title"],
                employment_type=data["employment_type"],
                date_of_joining=data["date_of_joining"],
                user_id=data["user_id"],
                created_by=request.user.user_id,
            )
        )
        return success_response(EmployeeResponseSerializer(result).data, status_code=201)

    @extend_schema(
        summary="Update an employee",
        description="Full-replace update of an employee record. Requires employees.manage_employees.",
        request=UpdateEmployeeSerializer,
        responses={200: EmployeeResponseSerializer},
    )
    def update(self, request: Request, pk: uuid.UUID | None = None, *args, **kwargs) -> Response:
        serializer = UpdateEmployeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = self.get_service().update_employee(
            UpdateEmployeeRequest(
                employee_id=pk,
                first_name=data["first_name"],
                last_name=data["last_name"],
                date_of_birth=data["date_of_birth"],
                gender=data["gender"],
                work_email=data["work_email"],
                personal_email=data["personal_email"],
                phone_number=data["phone_number"],
                department_id=data["department_id"],
                manager_id=data["manager_id"],
                job_title=data["job_title"],
                employment_type=data["employment_type"],
                date_of_joining=data["date_of_joining"],
                termination_date=data["termination_date"],
                updated_by=request.user.user_id,
            )
        )
        return success_response(EmployeeResponseSerializer(result).data)

    @extend_schema(
        summary="Get my own employee profile",
        description="Self-service (Phase 7): returns the employee record linked to the caller's "
        "own User account, with department_name/manager_name resolved. Requires only "
        "authentication, not employees.view_employees. 404 employee_not_found if the caller's "
        "User isn't linked to any employee record.",
        responses={200: EmployeeResponseSerializer},
    )
    def me(self, request: Request, *args, **kwargs) -> Response:
        result = self.get_service().get_my_profile(request.user.user_id)
        return success_response(EmployeeResponseSerializer(result).data)

    @extend_schema(
        summary="Search employees",
        description="Same mechanism as list, with a required free-text `q`/`search` "
        "query parameter matched against name, employee code, and work email.",
        responses={200: EmployeeResponseSerializer(many=True)},
    )
    def search(self, request: Request, *args, **kwargs) -> Response:
        # Deliberately just calls list() — see
        # apps/employees/application/services/employee_query_service.py's
        # docstring on why "list" and "search" are one mechanism, not two.
        return self.list(request, *args, **kwargs)

    @extend_schema(
        summary="Activate an employee",
        description="ACTIVE <- SUSPENDED/ON_LEAVE. Requires employees.manage_employees.",
        request=None,
        responses={200: EmployeeResponseSerializer},
    )
    def activate(self, request: Request, pk: uuid.UUID | None = None, *args, **kwargs) -> Response:
        result = self.get_service().activate_employee(pk)
        return success_response(EmployeeResponseSerializer(result).data)

    @extend_schema(
        summary="Deactivate an employee",
        description="ACTIVE/ON_LEAVE -> SUSPENDED. Requires employees.manage_employees.",
        request=None,
        responses={200: EmployeeResponseSerializer},
    )
    def deactivate(self, request: Request, pk: uuid.UUID | None = None, *args, **kwargs) -> Response:
        result = self.get_service().deactivate_employee(pk)
        return success_response(EmployeeResponseSerializer(result).data)
