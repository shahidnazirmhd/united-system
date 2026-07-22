"""Leave HTTP endpoints.

Two parallel surfaces, both delegating to the exact same `LeaveService` —
no business logic is duplicated between them, only "how do we know which
employee this is" differs:

* Self-service / HR (this file's `*View` classes without `Telegram` in the
  name) — JWT-authenticated (`IsAuthenticated`/`HasPermission`), employee
  resolved from `request.user.user_id` for "my own" endpoints, or taken as
  a path parameter (gated by `leave.view_leave`) for HR/Manager oversight.
* Gateway-facing (`*TelegramView` classes) — `HasInternalServiceKey`, no
  JWT, employee resolved from a `telegram_user_id` the Gateway supplies —
  mirrors `apps.employees.interface.telegram_views` exactly, including the
  `authentication_classes = []` discipline (see that file's docstring for
  why: DRF downgrades a failed permission check to 401 instead of 403 if
  any authenticator is configured but none succeeded).

Every method does exactly three things — deserialize, call the service,
serialize the result (CODING_STANDARD.md: "no business logic in views").
The one exception is the small ownership check on the two `*Detail*` views
below, which is authorization routing (object-level permission), not a
business rule — the business rule itself (can this request be cancelled at
all) still lives entirely in `LeaveRequestService`/domain entities.
"""
from __future__ import annotations

import uuid

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.leave.application.dtos import ApplyLeaveRequest, CancelLeaveRequest
from apps.leave.domain.exceptions import LeaveRequestOwnershipError
from apps.leave.interface import dependencies
from apps.leave.interface.permissions import VIEW_LEAVE, HasPermission
from apps.leave.interface.serializers import (
    ApplyLeaveSerializer,
    ApplyLeaveTelegramSerializer,
    CancelLeaveSerializer,
    CancelLeaveTelegramSerializer,
    LeaveBalanceResponseSerializer,
    LeaveHistoryQuerySerializer,
    LeaveRequestResponseSerializer,
    LeaveTypeResponseSerializer,
    TelegramLeaveBalanceQuerySerializer,
    TelegramLeaveHistoryQuerySerializer,
    TelegramUserIdQuerySerializer,
    YearQuerySerializer,
)
from shared_kernel.api.permissions import HasInternalServiceKey
from shared_kernel.api.response import paginated_response, success_response
from shared_kernel.api.throttling import StandardUserRateThrottle, TelegramLinkRateThrottle
from shared_kernel.domain.repository import QueryParams
from rest_framework.permissions import IsAuthenticated

# See apps/employees/interface/telegram_views.py's docstring for the full
# explanation of why this is required, not just permission_classes.
_NO_AUTHENTICATION: list = []


def _ensure_can_view(request: Request, resource_employee_id: uuid.UUID, caller_employee_id: uuid.UUID) -> None:
    """Object-level authorization for a single leave request/balance read:
    the caller may always see their own; seeing someone else's requires
    `leave.view_leave`. Raises the same `LeaveRequestOwnershipError`
    (422) `LeaveRequestService.cancel_leave` already uses for the
    equivalent write-side check, so both surfaces report ownership
    mismatches the same way."""
    if resource_employee_id == caller_employee_id:
        return
    principal = request.user
    if principal and principal.is_authenticated and principal.has_permission(VIEW_LEAVE):
        return
    raise LeaveRequestOwnershipError()


# ============================================================================
# Self-service / HR surface — JWT
# ============================================================================


class LeaveTypeListView(APIView):
    """GET /api/v1/leave/types/ — every active leave type. Any authenticated
    caller may read this; it's non-sensitive reference data."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(summary="List active leave types", responses={200: LeaveTypeResponseSerializer(many=True)})
    def get(self, request: Request) -> Response:
        result = dependencies.build_leave_service().list_leave_types()
        return success_response(LeaveTypeResponseSerializer(result, many=True).data)


class MyLeaveBalanceView(APIView):
    """GET /api/v1/leave/balance/me/?year=YYYY — the caller's own balance,
    one row per leave type."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Get my leave balance",
        parameters=[YearQuerySerializer],
        responses={200: LeaveBalanceResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = YearQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_user(request.user.user_id)
        result = service.list_balances(employee_id=employee_id, year=query.validated_data["year"])
        return success_response(LeaveBalanceResponseSerializer(result, many=True).data)


class EmployeeLeaveBalanceView(APIView):
    """GET /api/v1/leave/balance/<employee_id>/?year=YYYY — any employee's
    balance. Requires leave.view_leave (HR Admin/Manager territory)."""

    permission_classes = [HasPermission(VIEW_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Get an employee's leave balance",
        parameters=[YearQuerySerializer],
        responses={200: LeaveBalanceResponseSerializer(many=True)},
    )
    def get(self, request: Request, employee_id: uuid.UUID) -> Response:
        query = YearQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        result = dependencies.build_leave_service().list_balances(
            employee_id=employee_id, year=query.validated_data["year"]
        )
        return success_response(LeaveBalanceResponseSerializer(result, many=True).data)


class LeaveRequestListCreateView(APIView):
    """GET /api/v1/leave/requests/ — my own leave history (paginated).
    POST /api/v1/leave/requests/ — apply for leave (always "my own")."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="View my leave history",
        parameters=[LeaveHistoryQuerySerializer],
        responses={200: LeaveRequestResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = LeaveHistoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_user(request.user.user_id)
        filters = {"status": data["status"]} if data["status"] else {}
        page_result = service.list_history(
            employee_id=employee_id,
            query=QueryParams(filters=filters, page=data["page"], page_size=data["page_size"]),
        )
        serialized = LeaveRequestResponseSerializer(page_result.items, many=True).data
        return paginated_response(page_result, serialized)

    @extend_schema(
        summary="Apply for leave",
        description="Applies for leave on the caller's own behalf. Always creates status=pending — "
        "there is no approval workflow yet (Phase 8), so an applied request stays pending until a "
        "future Approval module acts on it.",
        request=ApplyLeaveSerializer,
        responses={201: LeaveRequestResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = ApplyLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_user(request.user.user_id)
        result = service.apply_leave(
            ApplyLeaveRequest(
                employee_id=employee_id,
                leave_type_id=data["leave_type_id"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                reason=data["reason"],
                created_by=request.user.user_id,
            )
        )
        return success_response(LeaveRequestResponseSerializer(result).data, status_code=201)


class EmployeeLeaveHistoryView(APIView):
    """GET /api/v1/leave/requests/employee/<employee_id>/ — any employee's
    leave history. Requires leave.view_leave."""

    permission_classes = [HasPermission(VIEW_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="View an employee's leave history",
        parameters=[LeaveHistoryQuerySerializer],
        responses={200: LeaveRequestResponseSerializer(many=True)},
    )
    def get(self, request: Request, employee_id: uuid.UUID) -> Response:
        query = LeaveHistoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        filters = {"status": data["status"]} if data["status"] else {}
        page_result = dependencies.build_leave_service().list_history(
            employee_id=employee_id,
            query=QueryParams(filters=filters, page=data["page"], page_size=data["page_size"]),
        )
        serialized = LeaveRequestResponseSerializer(page_result.items, many=True).data
        return paginated_response(page_result, serialized)


class LeaveRequestDetailView(APIView):
    """GET /api/v1/leave/requests/<pk>/ — view a single leave request. The
    caller's own, or any employee's if the caller holds leave.view_leave."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(summary="Get leave request details", responses={200: LeaveRequestResponseSerializer})
    def get(self, request: Request, pk: uuid.UUID) -> Response:
        service = dependencies.build_leave_service()
        result = service.get_request_detail(pk)
        caller_employee_id = service.resolve_employee_id_for_user(request.user.user_id)
        _ensure_can_view(request, result.employee_id, caller_employee_id)
        return success_response(LeaveRequestResponseSerializer(result).data)


class CancelLeaveRequestView(APIView):
    """POST /api/v1/leave/requests/<pk>/cancel/ — cancel the caller's own
    pending or approved leave request."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Cancel a leave request",
        request=CancelLeaveSerializer,
        responses={200: LeaveRequestResponseSerializer},
    )
    def post(self, request: Request, pk: uuid.UUID) -> Response:
        serializer = CancelLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_user(request.user.user_id)
        result = service.cancel_leave(
            CancelLeaveRequest(
                leave_request_id=pk,
                acting_employee_id=employee_id,
                cancellation_reason=serializer.validated_data["cancellation_reason"],
                cancelled_by=request.user.user_id,
            )
        )
        return success_response(LeaveRequestResponseSerializer(result).data)


# ============================================================================
# Telegram Gateway-facing surface — HasInternalServiceKey, no JWT
# ============================================================================


class LeaveTypesTelegramView(APIView):
    """GET /api/v1/leave/telegram/types/ — same data as LeaveTypeListView,
    Gateway-authenticated instead of JWT-authenticated."""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(summary="List active leave types (Telegram)", responses={200: LeaveTypeResponseSerializer(many=True)})
    def get(self, request: Request) -> Response:
        result = dependencies.build_leave_service().list_leave_types()
        return success_response(LeaveTypeResponseSerializer(result, many=True).data)


class LeaveBalanceTelegramView(APIView):
    """GET /api/v1/leave/telegram/balance/?telegram_user_id=...&year=..."""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="Get an employee's leave balance (Telegram)",
        parameters=[TelegramLeaveBalanceQuerySerializer],
        responses={200: LeaveBalanceResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = TelegramLeaveBalanceQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_telegram_user(data["telegram_user_id"])
        result = service.list_balances(employee_id=employee_id, year=data["year"])
        return success_response(LeaveBalanceResponseSerializer(result, many=True).data)


class LeaveHistoryTelegramView(APIView):
    """GET /api/v1/leave/telegram/requests/?telegram_user_id=...&status=..."""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="View leave history (Telegram)",
        parameters=[TelegramLeaveHistoryQuerySerializer],
        responses={200: LeaveRequestResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = TelegramLeaveHistoryQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_telegram_user(data["telegram_user_id"])
        filters = {"status": data["status"]} if data["status"] else {}
        page_result = service.list_history(
            employee_id=employee_id,
            query=QueryParams(filters=filters, page=data["page"], page_size=data["page_size"]),
        )
        serialized = LeaveRequestResponseSerializer(page_result.items, many=True).data
        return paginated_response(page_result, serialized)


class LeaveRequestDetailTelegramView(APIView):
    """GET /api/v1/leave/telegram/requests/<pk>/?telegram_user_id=..."""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]

    @extend_schema(
        summary="Get leave request details (Telegram)",
        parameters=[TelegramUserIdQuerySerializer],
        responses={200: LeaveRequestResponseSerializer},
    )
    def get(self, request: Request, pk: uuid.UUID) -> Response:
        query = TelegramUserIdQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_telegram_user(query.validated_data["telegram_user_id"])
        result = service.get_request_detail(pk)
        if result.employee_id != employee_id:
            raise LeaveRequestOwnershipError()
        return success_response(LeaveRequestResponseSerializer(result).data)


class ApplyLeaveTelegramView(APIView):
    """POST /api/v1/leave/telegram/requests/apply/"""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]
    throttle_classes = [TelegramLinkRateThrottle]

    @extend_schema(
        summary="Apply for leave (Telegram)", request=ApplyLeaveTelegramSerializer, responses={201: LeaveRequestResponseSerializer}
    )
    def post(self, request: Request) -> Response:
        serializer = ApplyLeaveTelegramSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_telegram_user(data["telegram_user_id"])
        result = service.apply_leave(
            ApplyLeaveRequest(
                employee_id=employee_id,
                leave_type_id=data["leave_type_id"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                reason=data["reason"],
            )
        )
        return success_response(LeaveRequestResponseSerializer(result).data, status_code=201)


class CancelLeaveTelegramView(APIView):
    """POST /api/v1/leave/telegram/requests/<pk>/cancel/"""

    authentication_classes = _NO_AUTHENTICATION
    permission_classes = [HasInternalServiceKey]
    throttle_classes = [TelegramLinkRateThrottle]

    @extend_schema(
        summary="Cancel a leave request (Telegram)",
        request=CancelLeaveTelegramSerializer,
        responses={200: LeaveRequestResponseSerializer},
    )
    def post(self, request: Request, pk: uuid.UUID) -> Response:
        serializer = CancelLeaveTelegramSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = dependencies.build_leave_service()
        employee_id = service.resolve_employee_id_for_telegram_user(data["telegram_user_id"])
        result = service.cancel_leave(
            CancelLeaveRequest(
                leave_request_id=pk,
                acting_employee_id=employee_id,
                cancellation_reason=data["cancellation_reason"],
            )
        )
        return success_response(LeaveRequestResponseSerializer(result).data)
