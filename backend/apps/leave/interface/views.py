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

from apps.leave.application.dtos import (
    AdjustLeaveBalanceRequest,
    ApplyLeaveRequest,
    CancelLeaveRequest,
    CreateLeaveTypeRequest,
    LeaveTypeListQuery,
    UpdateLeaveTypeRequest,
)
from apps.leave.domain.exceptions import LeaveRequestOwnershipError
from apps.leave.interface import dependencies
from apps.leave.interface.permissions import MANAGE_LEAVE, VIEW_LEAVE, HasPermission
from apps.leave.interface.serializers import (
    AdjustLeaveBalanceSerializer,
    ApplyLeaveSerializer,
    ApplyLeaveTelegramSerializer,
    CancelLeaveSerializer,
    CancelLeaveTelegramSerializer,
    CreateLeaveTypeSerializer,
    LeaveBalanceAdjustmentResponseSerializer,
    LeaveBalanceResponseSerializer,
    LeaveHistoryQuerySerializer,
    LeaveRequestResponseSerializer,
    LeaveTypeListQuerySerializer,
    LeaveTypeResponseSerializer,
    ManageLeaveRequestsQuerySerializer,
    TelegramLeaveBalanceQuerySerializer,
    TelegramLeaveHistoryQuerySerializer,
    TelegramUserIdQuerySerializer,
    UpdateLeaveTypeSerializer,
    YearQuerySerializer,
)
from shared_kernel.api.permissions import HasInternalServiceKey
from shared_kernel.api.response import paginated_response, success_response
from shared_kernel.api.throttling import StandardUserRateThrottle, TelegramLinkRateThrottle
from shared_kernel.domain.repository import PageResult, QueryParams
from rest_framework.permissions import IsAuthenticated

# See apps/employees/interface/telegram_views.py's docstring for the full
# explanation of why this is required, not just permission_classes.
_NO_AUTHENTICATION: list = []


def _ensure_can_view(
    request: Request, resource_employee_id: uuid.UUID, caller_employee_id: uuid.UUID | None
) -> None:
    """Object-level authorization for a single leave request/balance read:
    the caller may always see their own; seeing someone else's requires
    `leave.view_leave`. Raises the same `LeaveRequestOwnershipError`
    (422) `LeaveRequestService.cancel_leave` already uses for the
    equivalent write-side check, so both surfaces report ownership
    mismatches the same way.

    `caller_employee_id` is `None` for a caller with no linked Employee
    record at all (a pure Admin/HR account) — bugfix (round 16 item 2):
    this used to be resolved via the RAISING `resolve_employee_id_for_user`,
    which meant an HR/Admin account with `leave.view_leave` but no employee
    record of their own could never open ANY leave request's detail page
    (a 404 `LeaveEmployeeNotFoundError`, indistinguishable in the frontend
    from "this leave request doesn't exist"). A caller with no employee id
    of their own can never be viewing "their own" request, so this simply
    skips straight to the permission check below."""
    if caller_employee_id is not None and resource_employee_id == caller_employee_id:
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
        # `_or_none`, not the raising resolver: a caller with no linked
        # Employee record (a pure Admin/HR account) has zero balance rows —
        # that is an empty result for this READ endpoint, not a 404. See
        # `LeaveService.resolve_employee_id_for_user_or_none`'s docstring.
        employee_id = service.resolve_employee_id_for_user_or_none(request.user.user_id)
        if employee_id is None:
            return success_response([])
        result = service.list_balances(employee_id=employee_id, year=query.validated_data["year"])
        return success_response(LeaveBalanceResponseSerializer(result, many=True).data)


class EmployeeLeaveBalanceView(APIView):
    """GET /api/v1/leave/balance/<employee_id>/?year=YYYY — any employee's
    balance. Requires leave.view_leave (Admin, or any custom role granted
    it, territory)."""

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
        # `_or_none`, not the raising resolver: a caller with no linked
        # Employee record (a pure Admin/HR account) has zero leave requests
        # of their own — that is an empty page for this READ endpoint, not
        # a 404. See `LeaveService.resolve_employee_id_for_user_or_none`'s
        # docstring. `POST` on this same view (apply for leave) still uses
        # the raising resolver below — applying without an employee really
        # is an error.
        employee_id = service.resolve_employee_id_for_user_or_none(request.user.user_id)
        if employee_id is None:
            empty_page = PageResult(items=[], total_count=0, page=data["page"], page_size=data["page_size"])
            return paginated_response(empty_page, [])
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


class ManageLeaveRequestsView(APIView):
    """GET /api/v1/leave/requests/manage/ — every leave request across
    every employee (paginated, filterable) — Requires leave.view_leave.
    Backs the Leave module's HR-only processing queue (Phase 13 review
    requirement: the Leave tab is for processing applications, not for
    showing any one person's own leave — see LEAVE_API.md). Distinct from
    `LeaveRequestListCreateView` (self-service "my requests") and
    `EmployeeLeaveHistoryView` (one specific employee's history, used when
    HR has already picked someone) — this is the unscoped, whole-queue
    read the other two don't provide."""

    permission_classes = [HasPermission(VIEW_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="List leave requests across every employee (management)",
        description="Requires leave.view_leave. Every filter is optional.",
        parameters=[ManageLeaveRequestsQuerySerializer],
        responses={200: LeaveRequestResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = ManageLeaveRequestsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        filters: dict[str, object] = {}
        if data["employee_id"] is not None:
            filters["employee_id"] = data["employee_id"]
        if data["status"]:
            filters["status"] = data["status"]
        if data["leave_type_id"] is not None:
            filters["leave_type_id"] = data["leave_type_id"]
        if data["start_date_from"] is not None:
            filters["start_date__gte"] = data["start_date_from"]
        if data["start_date_to"] is not None:
            filters["start_date__lte"] = data["start_date_to"]

        page_result = dependencies.build_leave_service().list_all_requests_admin(
            query=QueryParams(filters=filters, page=data["page"], page_size=data["page_size"])
        )
        serialized = LeaveRequestResponseSerializer(page_result.items, many=True).data
        return paginated_response(page_result, serialized)


class AdjustLeaveBalanceView(APIView):
    """POST /api/v1/leave/balances/adjust/ — one upsert write path backing
    both named Phase 13 features: creates the balance row ("Opening" a new
    year/leave type) if none exists yet, or overwrites the existing row's
    absolute values ("Adjustment") otherwise — see
    `LeaveBalanceService.adjust_balance`'s docstring. Always writes an
    immutable audit row. Requires leave.manage_leave."""

    permission_classes = [HasPermission(MANAGE_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Adjust or open a leave balance",
        description="Requires leave.manage_leave. Creates the balance row if none exists yet for this "
        "employee/leave type/year (recorded as an 'opening'), or overwrites the existing row's absolute "
        "values (recorded as an 'adjustment'). Always writes an audit row.",
        request=AdjustLeaveBalanceSerializer,
        responses={200: LeaveBalanceAdjustmentResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = AdjustLeaveBalanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = dependencies.build_leave_service().adjust_balance(
            AdjustLeaveBalanceRequest(
                employee_id=data["employee_id"],
                leave_type_id=data["leave_type_id"],
                year=data["year"],
                entitled_days=data["entitled_days"],
                used_days=data["used_days"],
                carried_forward_days=data["carried_forward_days"],
                reason=data["reason"],
                adjusted_by=request.user.user_id,
            )
        )
        return success_response(LeaveBalanceAdjustmentResponseSerializer(result).data)


class ApplyLeaveForEmployeeView(APIView):
    """POST /api/v1/leave/requests/employee/<employee_id>/apply/ — HR/Admin
    applies for leave on a named employee's behalf. Requires
    leave.manage_leave. Delegates to the exact same `LeaveService.apply_leave`
    self-service uses — `ApplyLeaveRequest.employee_id` was already a free
    parameter at the service layer (see that DTO's docstring), so this view
    is the only new code this feature needed; the approval request that
    gets opened, and the Telegram notification the employee's own linked
    account receives once the manager decides, are identical to a
    self-submitted request, because `requested_by_employee_id` is always
    the leave owner (`created.employee_id`), never the caller
    (`LeaveRequestService.apply_leave`)."""

    permission_classes = [HasPermission(MANAGE_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Apply for leave on behalf of an employee",
        description="Requires leave.manage_leave. Same validation pipeline and approval workflow as "
        "self-service apply — see LeaveRequestService.apply_leave.",
        request=ApplyLeaveSerializer,
        responses={201: LeaveRequestResponseSerializer},
    )
    def post(self, request: Request, employee_id: uuid.UUID) -> Response:
        serializer = ApplyLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = dependencies.build_leave_service().apply_leave(
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


class CancelLeaveForEmployeeView(APIView):
    """POST /api/v1/leave/requests/<pk>/cancel-for-employee/ — HR/Admin
    cancels any employee's pending or approved leave request. Requires
    leave.manage_leave. Passes `acting_employee_id=None` — the documented
    bypass `CancelLeaveRequest`'s docstring reserves for an HR admin caller
    — since only a `leave.manage_leave`-holding caller can reach this view
    at all, the service-layer ownership check is correctly skipped here
    rather than duplicated (authorization already happened via
    `HasPermission(MANAGE_LEAVE)` above)."""

    permission_classes = [HasPermission(MANAGE_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Cancel any employee's leave request",
        description="Requires leave.manage_leave.",
        request=CancelLeaveSerializer,
        responses={200: LeaveRequestResponseSerializer},
    )
    def post(self, request: Request, pk: uuid.UUID) -> Response:
        serializer = CancelLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = dependencies.build_leave_service().cancel_leave(
            CancelLeaveRequest(
                leave_request_id=pk,
                acting_employee_id=None,
                cancellation_reason=serializer.validated_data["cancellation_reason"],
                cancelled_by=request.user.user_id,
            )
        )
        return success_response(LeaveRequestResponseSerializer(result).data)


class LeaveRequestDetailView(APIView):
    """GET /api/v1/leave/requests/<pk>/ — view a single leave request. The
    caller's own, or any employee's if the caller holds leave.view_leave."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(summary="Get leave request details", responses={200: LeaveRequestResponseSerializer})
    def get(self, request: Request, pk: uuid.UUID) -> Response:
        service = dependencies.build_leave_service()
        result = service.get_request_detail(pk)
        # `_or_none` — bugfix (round 16 item 2): see `_ensure_can_view`'s
        # docstring. A pure Admin/HR caller has no employee id of their own
        # to compare against, but must still be allowed through on
        # `leave.view_leave` alone.
        caller_employee_id = service.resolve_employee_id_for_user_or_none(request.user.user_id)
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


class ManageLeaveTypesView(APIView):
    """GET /api/v1/leave/types/manage/ — every leave type, active or not
    (paginated, searchable) — Requires leave.manage_leave. Distinct from
    GET /api/v1/leave/types/ (LeaveTypeListView above), which stays
    active-only/IsAuthenticated for every apply-leave dropdown; this is the
    admin management listing, matching how Department's list already
    differs from a plain employee-facing read.
    POST /api/v1/leave/types/manage/ — create a leave type."""

    permission_classes = [HasPermission(MANAGE_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="List leave types (management)",
        description="Every leave type, active or inactive. Requires leave.manage_leave.",
        parameters=[LeaveTypeListQuerySerializer],
        responses={200: LeaveTypeResponseSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        query = LeaveTypeListQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data

        page_result = dependencies.build_leave_service().list_leave_types_admin(
            LeaveTypeListQuery(
                is_active=data["is_active"], search=data["search"], page=data["page"], page_size=data["page_size"]
            )
        )
        serialized = LeaveTypeResponseSerializer(page_result.items, many=True).data
        return paginated_response(page_result, serialized)

    @extend_schema(
        summary="Create a leave type",
        description="Requires leave.manage_leave.",
        request=CreateLeaveTypeSerializer,
        responses={201: LeaveTypeResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = CreateLeaveTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = dependencies.build_leave_service().create_leave_type(
            CreateLeaveTypeRequest(
                name=data["name"],
                code=data["code"],
                default_annual_days=data["default_annual_days"],
                is_paid=data["is_paid"],
                requires_approval=data["requires_approval"],
                maps_to_employee_status=data.get("maps_to_employee_status"),
                created_by=request.user.user_id,
            )
        )
        return success_response(LeaveTypeResponseSerializer(result).data, status_code=201)


class LeaveTypeManageDetailView(APIView):
    """PATCH /api/v1/leave/types/manage/<pk>/ — full-replace update,
    including reactivating/deactivating via is_active. Requires
    leave.manage_leave. No delete — same "deactivate, don't hard-delete"
    precedent as Department (LeaveTypeRecord.leave_type is RESTRICT-
    constrained by both LeaveBalanceRecord and LeaveRequestRecord)."""

    permission_classes = [HasPermission(MANAGE_LEAVE)]
    throttle_classes = [StandardUserRateThrottle]

    @extend_schema(
        summary="Update a leave type",
        description="Full-replace update. Requires leave.manage_leave.",
        request=UpdateLeaveTypeSerializer,
        responses={200: LeaveTypeResponseSerializer},
    )
    def patch(self, request: Request, pk: uuid.UUID) -> Response:
        serializer = UpdateLeaveTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = dependencies.build_leave_service().update_leave_type(
            UpdateLeaveTypeRequest(
                leave_type_id=pk,
                name=data["name"],
                code=data["code"],
                default_annual_days=data["default_annual_days"],
                is_paid=data["is_paid"],
                requires_approval=data["requires_approval"],
                is_active=data["is_active"],
                maps_to_employee_status=data.get("maps_to_employee_status"),
                updated_by=request.user.user_id,
            )
        )
        return success_response(LeaveTypeResponseSerializer(result).data)


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
