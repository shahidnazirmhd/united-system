"""Unit tests for LeaveRequestService — the orchestrator. Composed with the
*real* LeaveValidationService/LeaveBalanceService (only their repository
dependencies are faked), so these tests exercise the whole apply/cancel/
approve/reject flow end-to-end at the application layer, with no Django and
no database.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.leave.application.dtos import (
    ApplyLeaveRequest,
    ApproveLeaveRequest,
    CancelLeaveRequest,
    RejectLeaveRequest,
)
from apps.leave.application.services.leave_balance_service import LeaveBalanceService
from apps.leave.application.services.leave_request_service import LeaveRequestService
from apps.leave.application.services.leave_validation_service import LeaveValidationService
from apps.leave.domain.entities import LeaveBalance, LeaveRequest, LeaveType
from apps.leave.domain.enums import LeaveRequestStatus
from apps.leave.domain.events import LeaveRequestApplied, LeaveRequestApproved, LeaveRequestCancelled, LeaveRequestRejected
from apps.leave.domain.exceptions import (
    InsufficientLeaveBalanceError,
    LeaveEmployeeNotFoundError,
    LeaveRequestNotCancellableError,
    LeaveRequestNotFoundError,
    LeaveRequestOwnershipError,
    OverlappingLeaveRequestError,
)
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork
from shared_kernel.domain.value_objects import DateRange


class FakeUnitOfWork(UnitOfWork):
    def commit(self):
        pass

    def rollback(self):
        pass


class FakeEventBus(EventBus):
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)

    def subscribe(self, event_type, handler):
        pass


class FakeEmployeeLookupPort:
    """Approval Engine (Phase 9): every employee passed in `existing_employee_ids`
    is auto-assigned a manager who is auto-linked to Telegram by default —
    keeps every pre-Phase-9 test in this file passing unmodified, since none
    of them care about manager/Telegram specifics; a test that DOES care
    passes `managers=`/`telegram_linked_employee_ids=` explicitly (see
    apps.leave.tests.unit.test_leave_validation_service for the dedicated
    validate_manager_available_for_approval tests).

    Round 14 item 6: every existing employee is eligible for leave by
    default too — a test that DOES care passes `ineligible_employee_ids=`
    explicitly (see test_leave_validation_service for the dedicated
    validate_employee_eligible_for_leave tests)."""

    def __init__(
        self,
        existing_employee_ids=None,
        *,
        managers: dict | None = None,
        telegram_linked_employee_ids: set | None = None,
        ineligible_employee_ids: set | None = None,
    ):
        self._existing = existing_employee_ids or set()
        self._managers = dict(managers or {})
        for employee_id in self._existing:
            self._managers.setdefault(employee_id, uuid.uuid4())
        self._telegram_linked = (
            set(telegram_linked_employee_ids)
            if telegram_linked_employee_ids is not None
            else set(self._managers.values())
        )
        self._ineligible = set(ineligible_employee_ids or set())

    def employee_exists(self, employee_id):
        return employee_id in self._existing

    def get_employee_id_by_user_id(self, user_id):
        raise NotImplementedError

    def get_employee_id_by_telegram_user_id(self, telegram_user_id):
        raise NotImplementedError

    def get_manager_employee_id(self, employee_id):
        return self._managers.get(employee_id)

    def is_employee_linked_to_telegram(self, employee_id):
        return employee_id in self._telegram_linked

    def get_employee_display_info(self, employee_id):
        return None

    def is_employee_eligible_for_leave(self, employee_id):
        return employee_id not in self._ineligible

    def list_employee_ids_on_leave_status(self):
        return []


class FakeSettingsLookupPort:
    """Round 14 item 6 — stands in for `apps.settings` via
    `SettingsLookupPort`. Default `week_off_weekday=6` (Sunday) matches the
    production seed default; every test in this file that doesn't care
    about the specific weekday just gets the production default."""

    def __init__(self, week_off_weekday: int = 6):
        self._week_off_weekday = week_off_weekday

    def get_default_week_off_weekday(self) -> int:
        return self._week_off_weekday


class FakeHolidayLookupPort:
    """Round 14 item 6 — stands in for `apps.attendance` via
    `HolidayLookupPort`. No holidays unless a test explicitly configures
    them."""

    def __init__(self, holiday_dates=None):
        self._holiday_dates = frozenset(holiday_dates or ())

    def get_holiday_dates_in_range(self, *, start_date, end_date):
        return frozenset(d for d in self._holiday_dates if start_date <= d <= end_date)


class FakeEmployeeStatusPort:
    """Round 14 item 8 — stands in for `apps.employees` via
    `EmployeeStatusPort`. Records every call rather than actually mutating
    anything, so a test can assert on `entered`/`exited` if it cares."""

    def __init__(self):
        self.entered: list[tuple] = []
        self.exited: list = []

    def enter_leave_status(self, employee_id, leave_status):
        self.entered.append((employee_id, leave_status))

    def exit_leave_status(self, employee_id):
        self.exited.append(employee_id)


class FakeLeaveNotificationPort:
    """Round 15 item 6 — stands in for the Telegram push channel via
    `LeaveNotificationPort`. Records every call rather than actually
    dispatching anything, so a test can assert on `notified` if it cares."""

    def __init__(self):
        self.notified: list[dict] = []

    def notify_leave_cancelled(self, *, employee_id, leave_request_id, summary, was_approved):
        self.notified.append(
            {
                "employee_id": employee_id,
                "leave_request_id": leave_request_id,
                "summary": summary,
                "was_approved": was_approved,
            }
        )


class FakeApprovalRequestPort:
    def __init__(self):
        self.created: list[dict] = []
        # Round 17 item 2 — records every `cancel_approval_request` call so
        # a test can assert `cancel_leave` always closes the approval side,
        # regardless of the leave request's own prior status.
        self.cancelled: list[dict] = []

    def create_approval_request(self, *, subject_id, requested_by_employee_id, subject_summary):
        self.created.append(
            {
                "subject_id": subject_id,
                "requested_by_employee_id": requested_by_employee_id,
                "subject_summary": subject_summary,
            }
        )

    def cancel_approval_request(self, *, subject_id, reason=None):
        self.cancelled.append({"subject_id": subject_id, "reason": reason})


class FakeLeaveTypeRepository:
    def __init__(self, leave_types=None):
        self._leave_types = list(leave_types or [])

    def get_by_id(self, leave_type_id):
        return next((lt for lt in self._leave_types if lt.id == leave_type_id), None)

    def get_by_code(self, code):
        return next((lt for lt in self._leave_types if lt.code == code), None)

    def list_active(self):
        return [lt for lt in self._leave_types if lt.is_active]

    def exists(self, leave_type_id):
        return any(lt.id == leave_type_id and lt.is_active for lt in self._leave_types)


class FakeLeaveBalanceRepository:
    def __init__(self, balances=None):
        self._balances = list(balances or [])

    def get_by_employee_leave_type_year(self, *, employee_id, leave_type_id, year):
        return next(
            (b for b in self._balances if b.employee_id == employee_id and b.leave_type_id == leave_type_id and b.year == year),
            None,
        )

    def list_by_employee(self, *, employee_id, year):
        return [b for b in self._balances if b.employee_id == employee_id and b.year == year]

    def get_by_id(self, entity_id):
        return next((b for b in self._balances if b.id == entity_id), None)

    def list(self, query):
        raise NotImplementedError

    def create(self, entity):
        self._balances.append(entity)
        return entity

    def update(self, entity):
        self._balances = [entity if b.id == entity.id else b for b in self._balances]
        return entity

    def delete(self, entity_id):
        self._balances = [b for b in self._balances if b.id != entity_id]

    def exists(self, entity_id):
        return any(b.id == entity_id for b in self._balances)


class FakeLeaveRequestRepository:
    def __init__(self, requests=None):
        self._requests = list(requests or [])

    def get_overlapping_for_employee(self, *, employee_id, date_range, exclude_request_id=None):
        active = (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED)
        return [
            r
            for r in self._requests
            if r.employee_id == employee_id and r.status in active and r.id != exclude_request_id and r.date_range.overlaps(date_range)
        ]

    def get_duplicate(self, *, employee_id, leave_type_id, date_range):
        active = (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED)
        return next(
            (
                r
                for r in self._requests
                if r.employee_id == employee_id
                and r.leave_type_id == leave_type_id
                and r.status in active
                and r.date_range.start_date == date_range.start_date
                and r.date_range.end_date == date_range.end_date
            ),
            None,
        )

    def sum_pending_days(self, *, employee_id, leave_type_id, year):
        return sum(
            (
                r.total_days
                for r in self._requests
                if r.employee_id == employee_id
                and r.leave_type_id == leave_type_id
                and r.status == LeaveRequestStatus.PENDING
                and r.date_range.start_date.year == year
            ),
            Decimal("0"),
        )

    def get_by_id(self, entity_id):
        return next((r for r in self._requests if r.id == entity_id), None)

    def list(self, query):
        raise NotImplementedError

    def create(self, entity):
        self._requests.append(entity)
        return entity

    def update(self, entity):
        self._requests = [entity if r.id == entity.id else r for r in self._requests]
        return entity

    def delete(self, entity_id):
        self._requests = [r for r in self._requests if r.id != entity_id]

    def exists(self, entity_id):
        return any(r.id == entity_id for r in self._requests)


def _leave_type(**overrides) -> LeaveType:
    return LeaveType(
        id=overrides.pop("id", uuid.uuid4()),
        name=overrides.pop("name", "Annual Leave"),
        code=overrides.pop("code", "ANNUAL"),
        default_annual_days=overrides.pop("default_annual_days", Decimal("20")),
        is_active=overrides.pop("is_active", True),
    )


def _build(
    *,
    employee_ids=None,
    leave_types=None,
    balances=None,
    requests=None,
    approval_requests=None,
    notifications=None,
) -> tuple[LeaveRequestService, FakeLeaveRequestRepository, FakeLeaveBalanceRepository, FakeEventBus]:
    leave_type_repo = FakeLeaveTypeRepository(leave_types or [])
    balance_repo = FakeLeaveBalanceRepository(balances or [])
    request_repo = FakeLeaveRequestRepository(requests or [])
    validation = LeaveValidationService(
        leave_type_repository=leave_type_repo,
        leave_balance_repository=balance_repo,
        leave_request_repository=request_repo,
        employee_lookup=FakeEmployeeLookupPort(employee_ids or set()),
    )
    balance_service = LeaveBalanceService(
        leave_balance_repository=balance_repo,
        leave_type_repository=leave_type_repo,
        leave_request_repository=request_repo,
        unit_of_work=FakeUnitOfWork(),
    )
    event_bus = FakeEventBus()
    service = LeaveRequestService(
        leave_request_repository=request_repo,
        leave_type_repository=leave_type_repo,
        validation_service=validation,
        balance_service=balance_service,
        unit_of_work=FakeUnitOfWork(),
        event_bus=event_bus,
        approval_requests=approval_requests if approval_requests is not None else FakeApprovalRequestPort(),
        settings_lookup=FakeSettingsLookupPort(),
        holiday_lookup=FakeHolidayLookupPort(),
        employee_status=FakeEmployeeStatusPort(),
        notifications=notifications if notifications is not None else FakeLeaveNotificationPort(),
    )
    return service, request_repo, balance_repo, event_bus


# --- apply_leave --------------------------------------------------------


def test_apply_leave_creates_pending_request_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=date.today().year + 1, entitled_days=Decimal("20")
    )
    service, requests, _balances, event_bus = _build(employee_ids={employee_id}, leave_types=[leave_type], balances=[balance])
    start = date(date.today().year + 1, 6, 1)
    end = date(date.today().year + 1, 6, 3)

    result = service.apply_leave(
        ApplyLeaveRequest(employee_id=employee_id, leave_type_id=leave_type.id, start_date=start, end_date=end, reason="Vacation")
    )

    assert result.status == "pending"
    assert result.total_days == Decimal("3")
    assert len(requests._requests) == 1
    assert any(isinstance(e, LeaveRequestApplied) for e in event_bus.published)


def test_apply_leave_raises_for_unknown_employee() -> None:
    leave_type = _leave_type()
    service, *_ = _build(employee_ids=set(), leave_types=[leave_type])

    with pytest.raises(LeaveEmployeeNotFoundError):
        service.apply_leave(
            ApplyLeaveRequest(
                employee_id=uuid.uuid4(),
                leave_type_id=leave_type.id,
                start_date=date.today() + timedelta(days=5),
                end_date=date.today() + timedelta(days=6),
            )
        )


def test_apply_leave_raises_for_insufficient_balance() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=date.today().year + 1, entitled_days=Decimal("1")
    )
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], balances=[balance])

    with pytest.raises(InsufficientLeaveBalanceError):
        service.apply_leave(
            ApplyLeaveRequest(
                employee_id=employee_id,
                leave_type_id=leave_type.id,
                start_date=date(date.today().year + 1, 6, 1),
                end_date=date(date.today().year + 1, 6, 5),  # 5 days requested, only 1 entitled
            )
        )


def test_apply_leave_opens_an_approval_request_via_the_approvals_port() -> None:
    """Approval Engine (Phase 9): apply_leave must call
    ApprovalRequestPort.create_approval_request with the newly-created
    LeaveRequest's id, the applicant's employee id, and a non-empty
    subject_summary — proves the Leave -> Approvals wiring without needing
    the real apps.approvals module at all (FakeApprovalRequestPort stands
    in for ApprovalServiceRequestAdapter)."""
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=date.today().year + 1, entitled_days=Decimal("20")
    )
    leave_type_repo = FakeLeaveTypeRepository([leave_type])
    balance_repo = FakeLeaveBalanceRepository([balance])
    request_repo = FakeLeaveRequestRepository([])
    approval_port = FakeApprovalRequestPort()
    validation = LeaveValidationService(
        leave_type_repository=leave_type_repo,
        leave_balance_repository=balance_repo,
        leave_request_repository=request_repo,
        employee_lookup=FakeEmployeeLookupPort({employee_id}),
    )
    balance_service = LeaveBalanceService(
        leave_balance_repository=balance_repo,
        leave_type_repository=leave_type_repo,
        leave_request_repository=request_repo,
        unit_of_work=FakeUnitOfWork(),
    )
    service = LeaveRequestService(
        leave_request_repository=request_repo,
        leave_type_repository=leave_type_repo,
        validation_service=validation,
        balance_service=balance_service,
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
        approval_requests=approval_port,
        settings_lookup=FakeSettingsLookupPort(),
        holiday_lookup=FakeHolidayLookupPort(),
        employee_status=FakeEmployeeStatusPort(),
        notifications=FakeLeaveNotificationPort(),
    )
    start, end = date(date.today().year + 1, 6, 1), date(date.today().year + 1, 6, 3)

    result = service.apply_leave(
        ApplyLeaveRequest(employee_id=employee_id, leave_type_id=leave_type.id, start_date=start, end_date=end)
    )

    assert len(approval_port.created) == 1
    created = approval_port.created[0]
    assert created["subject_id"] == result.id
    assert created["requested_by_employee_id"] == employee_id
    assert leave_type.name in created["subject_summary"]


def test_apply_leave_raises_for_no_manager_assigned() -> None:
    from apps.leave.domain.exceptions import NoManagerAssignedError

    employee_id, leave_type = uuid.uuid4(), _leave_type()
    leave_type_repo = FakeLeaveTypeRepository([leave_type])
    balance_repo = FakeLeaveBalanceRepository([])
    request_repo = FakeLeaveRequestRepository([])
    validation = LeaveValidationService(
        leave_type_repository=leave_type_repo,
        leave_balance_repository=balance_repo,
        leave_request_repository=request_repo,
        employee_lookup=FakeEmployeeLookupPort({employee_id}, managers={employee_id: None}),
    )
    balance_service = LeaveBalanceService(
        leave_balance_repository=balance_repo,
        leave_type_repository=leave_type_repo,
        leave_request_repository=request_repo,
        unit_of_work=FakeUnitOfWork(),
    )
    service = LeaveRequestService(
        leave_request_repository=request_repo,
        leave_type_repository=leave_type_repo,
        validation_service=validation,
        balance_service=balance_service,
        unit_of_work=FakeUnitOfWork(),
        event_bus=FakeEventBus(),
        approval_requests=FakeApprovalRequestPort(),
        settings_lookup=FakeSettingsLookupPort(),
        holiday_lookup=FakeHolidayLookupPort(),
        employee_status=FakeEmployeeStatusPort(),
        notifications=FakeLeaveNotificationPort(),
    )

    with pytest.raises(NoManagerAssignedError):
        service.apply_leave(
            ApplyLeaveRequest(
                employee_id=employee_id,
                leave_type_id=leave_type.id,
                start_date=date.today() + timedelta(days=5),
                end_date=date.today() + timedelta(days=6),
            )
        )
    assert request_repo._requests == []  # aborted before the LeaveRequest was ever created


def test_apply_leave_raises_for_overlapping_existing_request() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    existing = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 5)),
        status=LeaveRequestStatus.PENDING,
    )
    balance = LeaveBalance(id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("30"))
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[existing])

    with pytest.raises(OverlappingLeaveRequestError):
        service.apply_leave(
            ApplyLeaveRequest(employee_id=employee_id, leave_type_id=leave_type.id, start_date=date(year, 6, 4), end_date=date(year, 6, 8))
        )


# --- cancel_leave --------------------------------------------------------


def test_cancel_leave_by_owner_succeeds_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 3)),
        status=LeaveRequestStatus.PENDING,
    )
    service, requests, _balances, event_bus = _build(employee_ids={employee_id}, leave_types=[leave_type], requests=[pending])

    result = service.cancel_leave(
        CancelLeaveRequest(leave_request_id=pending.id, acting_employee_id=employee_id, cancellation_reason="Plans changed")
    )

    assert result.status == "cancelled"
    assert any(isinstance(e, LeaveRequestCancelled) for e in event_bus.published)


def test_cancel_leave_raises_ownership_error_for_different_employee() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.PENDING,
    )
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], requests=[pending])

    with pytest.raises(LeaveRequestOwnershipError):
        service.cancel_leave(CancelLeaveRequest(leave_request_id=pending.id, acting_employee_id=uuid.uuid4()))


def test_cancel_leave_raises_when_already_cancelled() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    cancelled = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.CANCELLED,
    )
    service, *_ = _build(employee_ids={employee_id}, leave_types=[leave_type], requests=[cancelled])

    with pytest.raises(LeaveRequestNotCancellableError):
        service.cancel_leave(CancelLeaveRequest(leave_request_id=cancelled.id, acting_employee_id=employee_id))


def test_cancel_leave_of_approved_request_restores_balance() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    approved = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 3)),  # 3 days
        status=LeaveRequestStatus.APPROVED,
        # Round 14 item 6 — balance mutation now uses working_days, not
        # total_days; this entity is constructed directly (bypassing
        # apply_leave's own working-day calculation), so it must be set
        # explicitly to match the 3 calendar days above (no week-off/
        # holiday in range for this test).
        working_days=Decimal("3"),
    )
    balance = LeaveBalance(
        id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("20"), used_days=Decimal("3")
    )
    service, _requests, balances, _events = _build(
        employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[approved]
    )

    service.cancel_leave(CancelLeaveRequest(leave_request_id=approved.id, acting_employee_id=employee_id))

    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=year)
    assert updated.used_days == Decimal("0")


def test_cancel_leave_raises_not_found_for_unknown_request() -> None:
    service, *_ = _build()

    with pytest.raises(LeaveRequestNotFoundError):
        service.cancel_leave(CancelLeaveRequest(leave_request_id=uuid.uuid4(), acting_employee_id=uuid.uuid4()))


# --- cancel_leave: round 17 items 2/3 -------------------------------------


def test_cancel_leave_of_pending_request_closes_its_approval_request() -> None:
    """Round 17 item 2 — cancelling a still-PENDING (not yet approved)
    leave request must also close its open approval request, not just the
    leave request itself, so no approver can later approve/reject it."""
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.PENDING,
    )
    approval_port = FakeApprovalRequestPort()
    service, *_ = _build(
        employee_ids={employee_id}, leave_types=[leave_type], requests=[pending], approval_requests=approval_port
    )

    service.cancel_leave(
        CancelLeaveRequest(leave_request_id=pending.id, acting_employee_id=employee_id, cancellation_reason="Changed my mind")
    )

    assert approval_port.cancelled == [{"subject_id": pending.id, "reason": "Changed my mind"}]


def test_cancel_leave_of_approved_request_also_closes_approval_request() -> None:
    """Round 17 item 2 — `cancel_approval_request` is called unconditionally
    on every cancellation, not just a still-pending one; the Approval
    Engine's own `get_pending_by_subject` lookup is what makes this a
    no-op for a request whose approval chain already finished."""
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    approved = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.APPROVED,
        working_days=Decimal("2"),
    )
    approval_port = FakeApprovalRequestPort()
    service, *_ = _build(
        employee_ids={employee_id}, leave_types=[leave_type], requests=[approved], approval_requests=approval_port
    )

    service.cancel_leave(CancelLeaveRequest(leave_request_id=approved.id, acting_employee_id=employee_id))

    assert approval_port.cancelled == [{"subject_id": approved.id, "reason": None}]


def test_cancel_leave_of_pending_request_notifies_employee_with_was_approved_false() -> None:
    """Round 17 item 3 — notification now fires for a still-pending
    cancellation too (previously gated behind `if was_approved:`), with
    `was_approved=False` so the recipient sees the right wording."""
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.PENDING,
    )
    notifications = FakeLeaveNotificationPort()
    service, *_ = _build(
        employee_ids={employee_id}, leave_types=[leave_type], requests=[pending], notifications=notifications
    )

    service.cancel_leave(CancelLeaveRequest(leave_request_id=pending.id, acting_employee_id=employee_id))

    assert len(notifications.notified) == 1
    assert notifications.notified[0]["employee_id"] == employee_id
    assert notifications.notified[0]["was_approved"] is False


def test_cancel_leave_of_approved_request_notifies_employee_with_was_approved_true() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    approved = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date.today() + timedelta(days=5), end_date=date.today() + timedelta(days=6)),
        status=LeaveRequestStatus.APPROVED,
        working_days=Decimal("2"),
    )
    notifications = FakeLeaveNotificationPort()
    service, *_ = _build(
        employee_ids={employee_id}, leave_types=[leave_type], requests=[approved], notifications=notifications
    )

    service.cancel_leave(CancelLeaveRequest(leave_request_id=approved.id, acting_employee_id=employee_id))

    assert len(notifications.notified) == 1
    assert notifications.notified[0]["was_approved"] is True


# --- approve / reject (Approval module extension point) ------------------


def test_approve_increases_used_days_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 4)),  # 4 days
        status=LeaveRequestStatus.PENDING,
        # Round 14 item 6 — see test_cancel_leave_of_approved_request_restores_balance's
        # identical comment on why this must be set explicitly here.
        working_days=Decimal("4"),
    )
    balance = LeaveBalance(id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("20"))
    approver_id = uuid.uuid4()
    service, _requests, balances, event_bus = _build(
        employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[pending]
    )

    result = service.approve(ApproveLeaveRequest(leave_request_id=pending.id, approved_by=approver_id, comments="OK"))

    assert result.status == "approved"
    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=year)
    assert updated.used_days == Decimal("4")
    assert any(isinstance(e, LeaveRequestApproved) for e in event_bus.published)


def test_reject_does_not_change_balance_and_publishes_event() -> None:
    employee_id, leave_type = uuid.uuid4(), _leave_type()
    year = date.today().year + 1
    pending = LeaveRequest(
        id=uuid.uuid4(),
        employee_id=employee_id,
        leave_type_id=leave_type.id,
        date_range=DateRange(start_date=date(year, 6, 1), end_date=date(year, 6, 4)),
        status=LeaveRequestStatus.PENDING,
    )
    balance = LeaveBalance(id=uuid.uuid4(), employee_id=employee_id, leave_type_id=leave_type.id, year=year, entitled_days=Decimal("20"))
    service, _requests, balances, event_bus = _build(
        employee_ids={employee_id}, leave_types=[leave_type], balances=[balance], requests=[pending]
    )

    result = service.reject(RejectLeaveRequest(leave_request_id=pending.id, comments="Insufficient coverage"))

    assert result.status == "rejected"
    updated = balances.get_by_employee_leave_type_year(employee_id=employee_id, leave_type_id=leave_type.id, year=year)
    assert updated.used_days == Decimal("0")
    assert any(isinstance(e, LeaveRequestRejected) for e in event_bus.published)


def test_get_by_id_enriched_raises_not_found_for_unknown_request() -> None:
    service, *_ = _build()

    with pytest.raises(LeaveRequestNotFoundError):
        service.get_by_id_enriched(uuid.uuid4())
