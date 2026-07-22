"""Write side (Apply/Cancel + the Approval extension point) and detail/
history reads for Leave requests.

Extends `BaseService[LeaveRequest]` for `get_by_id`/`list` (View Leave
Request Details / View Leave History — genuinely uniform reads, exactly
the shape `BaseService` was built for) but bypasses `BaseService.create`/
`update` entirely for `apply_leave`/`cancel_leave`/`approve`/`reject` — a
leave application is not a plain-CRUD create (it runs a multi-step
validation pipeline via `LeaveValidationService` and touches
`LeaveBalanceService` too), matching exactly the same judgment call
`EmployeeCommandService.activate_employee`/`deactivate_employee` already
made for non-CRUD state transitions (see this phase's architecture notes).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from apps.leave.application.dtos import (
    ApplyLeaveRequest,
    ApproveLeaveRequest,
    CancelLeaveRequest,
    LeaveRequestResponse,
    RejectLeaveRequest,
)
from apps.leave.application.mappers import leave_request_to_response
from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.application.services.leave_validation_service import LeaveValidationService
from apps.leave.domain.entities import LeaveRequest
from apps.leave.domain.events import (
    LeaveRequestApplied,
    LeaveRequestApproved,
    LeaveRequestCancelled,
    LeaveRequestRejected,
)
from apps.leave.domain.exceptions import LeaveRequestNotFoundError, LeaveRequestOwnershipError
from apps.leave.domain.repositories import LeaveRequestRepository, LeaveTypeRepository
from shared_kernel.application.base_service import BaseService
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.infrastructure.uuid7 import generate_uuid7

logger = logging.getLogger(__name__)


class LeaveRequestService(BaseService[LeaveRequest]):
    not_found_exception = LeaveRequestNotFoundError

    def __init__(
        self,
        leave_request_repository: LeaveRequestRepository,
        leave_type_repository: LeaveTypeRepository,
        validation_service: LeaveValidationService,
        balance_service: LeaveBalanceService,
        unit_of_work: UnitOfWork,
        event_bus: EventBus,
    ) -> None:
        super().__init__(repository=leave_request_repository, unit_of_work=unit_of_work, event_bus=event_bus)
        self._requests = leave_request_repository
        self._leave_types = leave_type_repository
        self._validate = validation_service
        self._balances = balance_service

    # --- reads (get_by_id/list inherited from BaseService) --------------
    def get_by_id_enriched(self, leave_request_id: uuid.UUID) -> LeaveRequestResponse:
        request = self.get_by_id(leave_request_id)  # raises LeaveRequestNotFoundError
        return self.to_enriched_response(request)

    def to_enriched_response(self, request: LeaveRequest) -> LeaveRequestResponse:
        leave_type = self._leave_types.get_by_id(request.leave_type_id)
        return leave_request_to_response(request, leave_type_name=leave_type.name if leave_type is not None else None)

    # --- writes -----------------------------------------------------
    def apply_leave(self, request: ApplyLeaveRequest) -> LeaveRequestResponse:
        """Full validation pipeline, in order: employee exists -> leave
        type exists/active -> date range is valid -> start date isn't in
        the past (unless configured to allow it) -> no exact duplicate ->
        no overlap with any other active request -> sufficient balance.
        Each step raises its own specific exception on failure — see
        `LeaveValidationService`.
        """
        try:
            self._validate.validate_employee_exists(request.employee_id)
            leave_type = self._validate.validate_and_get_leave_type(request.leave_type_id)
            date_range = self._validate.build_date_range(request.start_date, request.end_date)
            self._validate.validate_not_past(request.start_date)
            self._validate.validate_no_duplicate(
                employee_id=request.employee_id, leave_type_id=request.leave_type_id, date_range=date_range
            )
            self._validate.validate_no_overlap(employee_id=request.employee_id, date_range=date_range)
            self._validate.validate_sufficient_balance(
                employee_id=request.employee_id,
                leave_type_id=request.leave_type_id,
                year=date_range.start_date.year,
                requested_days=Decimal(date_range.days),
            )
        except Exception:
            logger.warning(
                "Leave application rejected for employee=%s leave_type=%s (%s..%s)",
                request.employee_id,
                request.leave_type_id,
                request.start_date,
                request.end_date,
                exc_info=True,
            )
            raise

        leave_request = LeaveRequest(
            id=generate_uuid7(),
            employee_id=request.employee_id,
            leave_type_id=request.leave_type_id,
            date_range=date_range,
            reason=request.reason,
        )
        with self._uow:
            created = self._requests.create(leave_request)
        self._event_bus.publish(
            LeaveRequestApplied(
                leave_request_id=created.id,
                employee_id=created.employee_id,
                leave_type_id=created.leave_type_id,
                start_date=created.date_range.start_date,
                end_date=created.date_range.end_date,
            )
        )
        logger.info(
            "Leave applied: request=%s employee=%s leave_type=%s %s..%s (%s day(s))",
            created.id,
            created.employee_id,
            created.leave_type_id,
            created.date_range.start_date,
            created.date_range.end_date,
            created.total_days,
        )
        return self.to_enriched_response(created)

    def cancel_leave(self, request: CancelLeaveRequest) -> LeaveRequestResponse:
        existing = self.get_by_id(request.leave_request_id)  # raises LeaveRequestNotFoundError

        if request.acting_employee_id is not None and existing.employee_id != request.acting_employee_id:
            raise LeaveRequestOwnershipError()

        was_approved = existing.status.value == "approved"
        try:
            cancelled = existing.cancel(
                cancelled_at=datetime.now(timezone.utc), reason=request.cancellation_reason
            )
        except Exception:
            logger.warning("Leave cancellation rejected for request=%s", request.leave_request_id, exc_info=True)
            raise

        with self._uow:
            saved = self._requests.update(cancelled)
        if was_approved:
            self._balances.decrease_used_days(
                employee_id=saved.employee_id,
                leave_type_id=saved.leave_type_id,
                year=saved.date_range.start_date.year,
                amount=saved.total_days,
            )
        self._event_bus.publish(LeaveRequestCancelled(leave_request_id=saved.id, employee_id=saved.employee_id))
        logger.info("Leave cancelled: request=%s employee=%s", saved.id, saved.employee_id)
        return self.to_enriched_response(saved)

    # --- Approval module extension point ---------------------------
    # Not called by any interface-layer code this phase — see this
    # module's architecture notes ("Approval Preparation"). Implemented
    # and unit-tested now so the future Approval module has a correct,
    # ready-made integration point rather than needing changes to this
    # module when it's built.
    def approve(self, request: ApproveLeaveRequest) -> LeaveRequestResponse:
        existing = self.get_by_id(request.leave_request_id)
        approved = existing.approve(
            approved_by=request.approved_by, decided_at=datetime.now(timezone.utc), comments=request.comments
        )
        with self._uow:
            saved = self._requests.update(approved)
        self._balances.increase_used_days(
            employee_id=saved.employee_id,
            leave_type_id=saved.leave_type_id,
            year=saved.date_range.start_date.year,
            amount=saved.total_days,
        )
        self._event_bus.publish(
            LeaveRequestApproved(leave_request_id=saved.id, employee_id=saved.employee_id, approved_by=saved.approved_by)
        )
        logger.info("Leave approved: request=%s employee=%s by=%s", saved.id, saved.employee_id, saved.approved_by)
        return self.to_enriched_response(saved)

    def reject(self, request: RejectLeaveRequest) -> LeaveRequestResponse:
        existing = self.get_by_id(request.leave_request_id)
        rejected = existing.reject(decided_at=datetime.now(timezone.utc), comments=request.comments)
        with self._uow:
            saved = self._requests.update(rejected)
        self._event_bus.publish(LeaveRequestRejected(leave_request_id=saved.id, employee_id=saved.employee_id))
        logger.info("Leave rejected: request=%s employee=%s", saved.id, saved.employee_id)
        return self.to_enriched_response(saved)
