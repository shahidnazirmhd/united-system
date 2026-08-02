"""Write side of Leave Type Management (Phase 13).

Built on `BaseService`, the same choice `DepartmentCommandService` made in
Phase 12 and for the identical reason: this is CRUD-plus-a-code-uniqueness-
check, not a set of genuinely distinct actions requiring Identity's
one-class-per-use-case style. Reads stay on `LeaveTypeRepository` directly
(`list_active`/`get_by_code`) or, for the admin "see every leave type"
listing, on this class's own `list_all` — there is no cross-entity name
resolution `LeaveType` needs (unlike Department's parent/head), so no
separate query-service split was warranted here.
"""
from __future__ import annotations

from apps.leave.application.dtos import (
    CreateLeaveTypeRequest,
    LeaveTypeListQuery,
    LeaveTypeResponse,
    UpdateLeaveTypeRequest,
)
from apps.leave.application.mappers import leave_type_to_response
from apps.leave.domain.employee_status_mapping import ALLOWED_EMPLOYEE_STATUS_MAPPINGS
from apps.leave.domain.entities import LeaveType
from apps.leave.domain.exceptions import (
    DuplicateLeaveTypeCodeError,
    InvalidEmployeeStatusMappingError,
    LeaveTypeNotFoundError,
    LeaveTypeReferencedByLeaveRequestError,
)
from apps.leave.domain.repositories import LeaveRequestRepository, LeaveTypeRepository
from shared_kernel.application.base_service import BaseService
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.repository import PageResult, QueryParams
from shared_kernel.infrastructure.uuid7 import generate_uuid7

_SEARCH_FIELDS = ("name", "code")
_DEFAULT_ORDERING = ("name",)


class LeaveTypeService(BaseService[LeaveType]):
    not_found_exception = LeaveTypeNotFoundError

    def __init__(
        self,
        leave_type_repository: LeaveTypeRepository,
        unit_of_work: UnitOfWork,
        leave_request_repository: LeaveRequestRepository | None = None,
    ) -> None:
        super().__init__(repository=leave_type_repository, unit_of_work=unit_of_work)
        self._leave_types = leave_type_repository
        # Round 15 item 5 — same-module referential-integrity check
        # (Leave owns both sides here, unlike Holiday/Default Week Off's
        # reverse-port versions of this same rule), so this is a direct
        # repository dependency, not a port. Optional (default None) so
        # any existing test construction of this service keeps working
        # unchanged.
        self._leave_requests = leave_request_repository

    # --- reads (admin listing — includes inactive rows) -----------------
    def list_all(self, query: LeaveTypeListQuery) -> PageResult[LeaveTypeResponse]:
        filters: dict[str, object] = {}
        if query.is_active is not None:
            filters["is_active"] = query.is_active

        page_result = self._leave_types.list(
            QueryParams(
                filters=filters,
                search=query.search,
                search_fields=_SEARCH_FIELDS,
                ordering=query.ordering or _DEFAULT_ORDERING,
                page=query.page,
                page_size=query.page_size,
            )
        )
        return PageResult(
            items=[leave_type_to_response(lt) for lt in page_result.items],
            total_count=page_result.total_count,
            page=page_result.page,
            page_size=page_result.page_size,
        )

    # --- writes -----------------------------------------------------
    def create_leave_type(self, request: CreateLeaveTypeRequest) -> LeaveTypeResponse:
        leave_type = LeaveType(
            id=generate_uuid7(),
            name=request.name,
            code=request.code,
            default_annual_days=request.default_annual_days,
            is_paid=request.is_paid,
            requires_approval=request.requires_approval,
            maps_to_employee_status=request.maps_to_employee_status,
        )
        created = self.create(leave_type)  # validate_create -> uow -> repository.create
        return leave_type_to_response(created)

    def update_leave_type(self, request: UpdateLeaveTypeRequest) -> LeaveTypeResponse:
        self.get_by_id(request.leave_type_id)  # raises LeaveTypeNotFoundError if missing
        updated_entity = LeaveType(
            id=request.leave_type_id,
            name=request.name,
            code=request.code,
            default_annual_days=request.default_annual_days,
            is_paid=request.is_paid,
            requires_approval=request.requires_approval,
            is_active=request.is_active,
            maps_to_employee_status=request.maps_to_employee_status,
        )
        updated = self.update(updated_entity)  # validate_update -> uow -> repository.update
        return leave_type_to_response(updated)

    # --- BaseService hooks ----------------------------------------------
    def validate_create(self, entity: LeaveType) -> None:
        if self._leave_types.get_by_code(entity.code) is not None:
            raise DuplicateLeaveTypeCodeError()
        self._validate_employee_status_mapping(entity)

    def validate_update(self, entity: LeaveType) -> None:
        holder = self._leave_types.get_by_code(entity.code)
        if holder is not None and holder.id != entity.id:
            raise DuplicateLeaveTypeCodeError()
        self._validate_employee_status_mapping(entity)
        # Round 15 item 5 — block ANY edit (including deactivation; there
        # is no delete endpoint, see LeaveTypeManageDetailView's docstring)
        # to a leave type still referenced by a real PENDING/APPROVED leave
        # request. `entity.id` is the leave type's own (unchanged-on-update)
        # id, so no separate "fetch the existing row" lookup is needed here
        # (unlike Holiday's version of this same rule, where the date
        # itself can change).
        if self._leave_requests is not None and self._leave_requests.exists_active_request_for_leave_type(entity.id):
            raise LeaveTypeReferencedByLeaveRequestError()

    def _validate_employee_status_mapping(self, entity: LeaveType) -> None:
        if (
            entity.maps_to_employee_status is not None
            and entity.maps_to_employee_status not in ALLOWED_EMPLOYEE_STATUS_MAPPINGS
        ):
            raise InvalidEmployeeStatusMappingError()
