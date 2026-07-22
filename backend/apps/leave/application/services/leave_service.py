"""Facade composing Leave's services into the single object the interface
layer depends on — matches `apps.employees.application.services.employee_service.EmployeeService`'s
role exactly: delegation only, so a ViewSet/View holds one dependency
instead of four.
"""
from __future__ import annotations

import uuid
from datetime import date

from apps.leave.application.dtos import (
    ApplyLeaveRequest,
    ApproveLeaveRequest,
    CancelLeaveRequest,
    LeaveBalanceResponse,
    LeaveRequestResponse,
    LeaveTypeResponse,
    RejectLeaveRequest,
)
from apps.leave.application.mappers import leave_type_to_response
from apps.leave.application.ports import EmployeeLookupPort
from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.application.services.leave_request_service import LeaveRequestService
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
    ) -> None:
        self._leave_types = leave_type_repository
        self._balances = balance_service
        self._requests = request_service
        self._employees = employee_lookup

    # --- caller resolution (self-service vs. Gateway) --------------------
    def resolve_employee_id_for_user(self, user_id: uuid.UUID) -> uuid.UUID:
        employee_id = self._employees.get_employee_id_by_user_id(user_id)
        if employee_id is None:
            raise LeaveEmployeeNotFoundError()
        return employee_id

    def resolve_employee_id_for_telegram_user(self, telegram_user_id: int) -> uuid.UUID:
        employee_id = self._employees.get_employee_id_by_telegram_user_id(telegram_user_id)
        if employee_id is None:
            raise LeaveEmployeeNotFoundError()
        return employee_id

    # --- Leave Types ------------------------------------------------
    def list_leave_types(self) -> list[LeaveTypeResponse]:
        return [leave_type_to_response(lt) for lt in self._leave_types.list_active()]

    # --- Leave Balance ------------------------------------------------
    def get_balance(self, *, employee_id: uuid.UUID, leave_type_id: uuid.UUID, year: int) -> LeaveBalanceResponse:
        return self._balances.get_balance(employee_id=employee_id, leave_type_id=leave_type_id, year=year)

    def list_balances(self, *, employee_id: uuid.UUID, year: int | None = None) -> list[LeaveBalanceResponse]:
        return self._balances.list_balances(employee_id=employee_id, year=year or date.today().year)

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

    # --- Approval module extension point (not wired to any endpoint) -----
    def approve_leave(self, request: ApproveLeaveRequest) -> LeaveRequestResponse:
        return self._requests.approve(request)

    def reject_leave(self, request: RejectLeaveRequest) -> LeaveRequestResponse:
        return self._requests.reject(request)
