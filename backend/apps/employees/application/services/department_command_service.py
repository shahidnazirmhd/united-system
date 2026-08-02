"""Write side of Department (Phase 12: Department CRUD).

Built on `BaseService`, same choice as `EmployeeCommandService` and for the
identical reason — this is CRUD-plus-a-couple-of-validations, not a set of
genuinely distinct actions requiring Identity's one-class-per-use-case
style. Split from `DepartmentQueryService`/`DepartmentService` (facade)
for the same reason Employee is split three ways: `BaseViewSet`'s generic
`list()`/`retrieve()` call `get_service().list(query)`/`.get_by_id(pk)`
expecting an *enriched* `DepartmentResponse` back (parent/head names
resolved) — `BaseService.get_by_id`/`.list` return raw `Department`
entities, which would break that serializer. See `department_service.py`'s
docstring for the full reasoning.
"""
from __future__ import annotations

from apps.employees.application.dtos import CreateDepartmentRequest, DepartmentResponse, UpdateDepartmentRequest
from apps.employees.application.mappers import department_to_response
from apps.employees.domain.entities import Department
from apps.employees.domain.exceptions import (
    DepartmentNotFoundError,
    DuplicateDepartmentCodeError,
    EmployeeNotFoundError,
    InvalidDepartmentParentError,
)
from apps.employees.domain.repositories import DepartmentRepository, EmployeeRepository
from shared_kernel.application.base_service import BaseService
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.repository import QueryParams
from shared_kernel.infrastructure.uuid7 import generate_uuid7


class DepartmentCommandService(BaseService[Department]):
    not_found_exception = DepartmentNotFoundError

    def __init__(
        self,
        department_repository: DepartmentRepository,
        employee_repository: EmployeeRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        super().__init__(repository=department_repository, unit_of_work=unit_of_work)
        self._departments = department_repository
        self._employees = employee_repository

    def create_department(self, request: CreateDepartmentRequest) -> DepartmentResponse:
        department = Department(
            id=generate_uuid7(),
            name=request.name,
            code=request.code,
            parent_department_id=request.parent_department_id,
            head_employee_id=request.head_employee_id,
        )
        created = self.create(department)  # validate_create -> uow -> repository.create
        return department_to_response(created)

    def update_department(self, request: UpdateDepartmentRequest) -> DepartmentResponse:
        self.get_by_id(request.department_id)  # raises DepartmentNotFoundError if missing
        updated_entity = Department(
            id=request.department_id,
            name=request.name,
            code=request.code,
            parent_department_id=request.parent_department_id,
            head_employee_id=request.head_employee_id,
            is_active=request.is_active,
        )
        updated = self.update(updated_entity)  # validate_update -> uow -> repository.update
        return department_to_response(updated)

    # --- BaseService hooks ----------------------------------------------
    def validate_create(self, entity: Department) -> None:
        self._validate_references(entity)
        if self._departments.exists_with_code(entity.code):
            raise DuplicateDepartmentCodeError()

    def validate_update(self, entity: Department) -> None:
        self._validate_references(entity)
        holder = self._find_by_code(entity.code)
        if holder is not None and holder.id != entity.id:
            raise DuplicateDepartmentCodeError()

    def _validate_references(self, entity: Department) -> None:
        if entity.parent_department_id is not None:
            if entity.parent_department_id == entity.id:
                raise InvalidDepartmentParentError("A department cannot be its own parent.")
            if not self._departments.exists(entity.parent_department_id):
                raise DepartmentNotFoundError()
        if entity.head_employee_id is not None and not self._employees.exists(entity.head_employee_id):
            raise EmployeeNotFoundError()

    def _find_by_code(self, code: str) -> Department | None:
        # DepartmentRepository has no get_by_code — nothing else needs one,
        # so a one-off exact-filter list() call here is clearer than adding
        # a lookup method to the shared ABC for a single caller.
        page = self._departments.list(QueryParams(filters={"code": code}, page_size=1))
        return page.items[0] if page.items else None
