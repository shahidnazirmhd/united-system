"""Facade composing Leave's services into the single object the interface
layer depends on — matches `apps.employees.application.services.employee_service.EmployeeService`'s
role exactly: delegation only, so a ViewSet/View holds one dependency
instead of four.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import date

from apps.leave.application.dtos import (
    AdjustLeaveBalanceRequest,
    ApplyLeaveRequest,
    ApproveLeaveRequest,
    CancelLeaveRequest,
    CreateLeaveTypeRequest,
    LeaveBalanceAdjustmentResponse,
    LeaveBalanceResponse,
    LeaveRequestResponse,
    LeaveTypeListQuery,
    LeaveTypeResponse,
    RejectLeaveRequest,
    UpdateLeaveTypeRequest,
)
from apps.leave.application.mappers import leave_type_to_response
from apps.leave.application.ports import EmployeeLookupPort
from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.application.services.leave_request_service import LeaveRequestService
from apps.leave.application.services.leave_type_service import LeaveTypeService
from apps.leave.domain.exceptions import LeaveEmployeeNotFoundError
from apps.leave.domain.repositories import LeaveTypeRepository
from shared_kernel.domain.repository import PageResult, QueryParams


class LeaveService:
    def __init__(
        self,
        leave_type_repository: LeaveTypeRepository,
        balance_service: LeaveBalanceService,
        request_service: LeaveRequestService,
        employee_lookup: EmployeeLookupPort,
        leave_type_service: LeaveTypeService,
    ) -> None:
        self._leave_types = leave_type_repository
        self._balances = balance_service
        self._requests = request_service
        self._employees = employee_lookup
        self._leave_type_admin = leave_type_service

    # --- caller resolution (self-service vs. Gateway) --------------------
    def resolve_employee_id_for_user(self, user_id: uuid.UUID) -> uuid.UUID:
        employee_id = self._employees.get_employee_id_by_user_id(user_id)
        if employee_id is None:
            raise LeaveEmployeeNotFoundError()
        return employee_id

    def resolve_employee_id_for_user_or_none(self, user_id: uuid.UUID) -> uuid.UUID | None:
        """Same lookup as `resolve_employee_id_for_user`, but never raises —
        for the "my own" READ endpoints only (`LeaveRequestListCreateView.get`,
        `MyLeaveBalanceView.get`). A caller with no linked Employee record
        (e.g. a pure Admin/HR account) trivially has zero leave requests and
        zero balance rows; that is an empty result, not an error. Any
        endpoint that WRITES on the caller's own behalf (apply_leave,
        cancel_leave, ...) must keep using the raising
        `resolve_employee_id_for_user` above — "no employee to apply leave
        for" is still a genuine error there."""
        return self._employees.get_employee_id_by_user_id(user_id)

    def resolve_employee_id_for_telegram_user(self, telegram_user_id: int) -> uuid.UUID:
        employee_id = self._employees.get_employee_id_by_telegram_user_id(telegram_user_id)
        if employee_id is None:
            raise LeaveEmployeeNotFoundError()
        return employee_id

    # --- Leave Types ------------------------------------------------
    def list_leave_types(self) -> list[LeaveTypeResponse]:
        return [leave_type_to_response(lt) for lt in self._leave_types.list_active()]

    # --- Leave Type Management (Phase 13, leave.manage_leave) -----------
    def list_leave_types_admin(self, query: LeaveTypeListQuery) -> PageResult[LeaveTypeResponse]:
        return self._leave_type_admin.list_all(query)

    def create_leave_type(self, request: CreateLeaveTypeRequest) -> LeaveTypeResponse:
        return self._leave_type_admin.create_leave_type(request)

    def update_leave_type(self, request: UpdateLeaveTypeRequest) -> LeaveTypeResponse:
        return self._leave_type_admin.update_leave_type(request)

    # --- Leave Balance ------------------------------------------------
    def get_balance(self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int) -> LeaveBalanceResponse:
        return self._balances.get_balance(employee_id=employee_id, leave_type_id=leave_type_id, year=year)

    def list_balances(self, *, employee_id: uuid.UUID, year: int | None = None) -> list[LeaveBalanceResponse]:
        return self._balances.list_balances(employee_id=employee_id, year=year or date.today().year)

    # --- Leave Balance Adjustment / Opening (Phase 13, leave.manage_leave) --
    def adjust_balance(self, request: AdjustLeaveBalanceRequest) -> LeaveBalanceAdjustmentResponse:
        return self._balances.adjust_balance(request)

    # --- Leave Requests ------------------------------------------------
    def apply_leave(self, request: ApplyLeaveRequest) -> LeaveRequestResponse:
        return self._requests.apply_leave(request)

    def cancel_leave(self, request: CancelLeaveRequest) -> LeaveRequestResponse:
        return self._requests.cancel_leave(request)

    def get_request_detail(self, leave_request_id: uuid.UUID) -> LeaveRequestResponse:
        return self._requests.get_by_id_enriched(leave_request_id)

    def list_history(self, *, employee_id: uuid.UUID, query: QueryParams) -> PageResult[LeaveRequestResponse]:
        filters = dict(query.filters)
        filters["employee_id"] = employee_id
        page_result = self._requests.list(
            QueryParams(
                filters=filters,
                ordering=query.ordering or ("-created_at",),
                page=query.page,
                page_size=query.page_size,
            )
        )
        return PageResult(
            items=[self._requests.to_enriched_response(r) for r in page_result.items],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )

    # --- HR-wide leave request queue (Phase 13 review requirement) -------
    def list_all_requests_admin(self, *, query: QueryParams) -> PageResult[LeaveRequestResponse]:
        """Every employee's leave requests, not scoped to one employee like
        `list_history` — backs the Leave module's HR-only processing queue.
        `query.filters` may optionally carry `employee_id` (exact match),
        `status`, `leave_type_id`, and/or date-range lookups
        (`start_date__gte`, `end_date__lte`, ...); see
        `interface/views.py::ManageLeaveRequestsView` for the exact filters
        exposed over HTTP."""
        page_result = self._requests.list(
            QueryParams(
                filters=dict(query.filters),
                ordering=query.ordering or ("-created_at",),
                page=query.page,
                page_size=query.page_size,
            )
        )
        return PageResult(
            items=[
                self._enrich_with_employee_display(self._requests.to_enriched_response(r))
                for r in page_result.items
            ],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )

    def _enrich_with_employee_display(self, response: LeaveRequestResponse) -> LeaveRequestResponse:
        """One `EmployeeLookupPort` call per row — bounded by page size
        (typically <=25-50), not total table size, since this only ever
        runs over one already-paginated page's worth of results. Every
        other Leave read already has employee context from its own caller
        (see `EmployeeLookupPort.get_employee_display_info`'s docstring),
        so this is the one place that needs it."""
        display = self._employees.get_employee_display_info(response.employee_id)
        if display is None:
            return response
        full_name, employee_code = display
        return replace(response, employee_name=full_name, employee_code=employee_code)

    # --- Approval module extension point (not wired to any endpoint) -----
    def approve_leave(self, request: ApproveLeaveRequest) -> LeaveRequestResponse:
        return self._requests.approve(request)

    def reject_leave(self, request: RejectLeaveRequest) -> LeaveRequestResponse:
        return self._requests.reject(request)

    # --- Cross-module referential-integrity checks (round 15 items 3/4) --
    # The one public entry point Attendance's and Settings' reverse ports
    # (see apps.attendance.application.ports.LeaveReferenceCheckPort and
    # apps.app_settings.application.ports.LeaveReferenceCheckPort) call
    # into — through this module's own composition root
    # (`build_leave_service`), never Leave's infrastructure directly, same
    # discipline every other cross-module adapter in this codebase follows.
    def has_active_request_covering_date(self, target_date: date) -> bool:
        return self._requests.has_active_request_covering_date(target_date)

    def has_any_active_request(self) -> bool:
        return self._requests.has_any_active_request()
