"""Unit tests for `ApprovalService` — the core, fully generic engine.
Every dependency is a hand-rolled fake; no Django database access. Same
discipline as apps/leave/tests/unit/test_leave_request_service.py.

These tests are what prove the "dynamic approval levels without modifying
the core Approval Engine" requirement: `FakeTwoLevelChainResolver` below
simulates a HYPOTHETICAL two-level subject module purely by how it answers
`resolve_next_approver` — no change to `ApprovalService` itself was needed
to support it.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from apps.approvals.application.dtos import (
    CancelApprovalRequestForSubjectRequest,
    CreateApprovalRequestRequest,
    DecideApprovalRequest,
)
from apps.approvals.application.registry import ApprovalChainResolverRegistry
from apps.approvals.application.services.approval_service import (
    DECISION_APPROVE,
    DECISION_REJECT,
    ApprovalService,
)
from apps.approvals.domain.enums import ApprovalChannel, ApprovalStatus, ApprovalStepStatus
from apps.approvals.domain.exceptions import (
    ApprovalChannelNotAllowedError,
    ApprovalRequestNotFoundError,
    ApprovalRequestNotPendingError,
    NoApprovalChainResolverRegisteredError,
    NoApproverAvailableError,
    NotTheAssignedApproverError,
)
from apps.approvals.domain.value_objects import ApproverAssignment
from shared_kernel.application.event_bus import EventBus
from shared_kernel.application.unit_of_work import UnitOfWork

_SUBJECT_TYPE = "leave.leave_request"
# Every real `DecideApprovalRequest` construction below that doesn't
# specifically test channel restriction just needs *some* valid, consistent
# channel — using the real `ApprovalChannel` values (not ad hoc strings)
# keeps these tests honest about what a real caller would send.
_WEB = ApprovalChannel.WEB.value
_TELEGRAM = ApprovalChannel.TELEGRAM.value


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


class FakeNotificationPort:
    def __init__(self):
        self.requested_calls = []
        self.decided_calls = []
        self.advanced_calls = []

    def notify_approval_requested(self, *, approver_employee_id, subject_summary, approval_request_id, level):
        self.requested_calls.append(
            {
                "approver_employee_id": approver_employee_id,
                "subject_summary": subject_summary,
                "approval_request_id": approval_request_id,
                "level": level,
            }
        )

    def notify_decision_made(self, *, requested_by_employee_id, subject_summary, final_status, comments, approval_request_id):
        self.decided_calls.append(
            {
                "requested_by_employee_id": requested_by_employee_id,
                "final_status": final_status,
                "comments": comments,
                "approval_request_id": approval_request_id,
            }
        )

    def notify_step_advanced(
        self, *, requested_by_employee_id, subject_summary, message, new_level, approval_request_id
    ):
        # Leave review round: the "manager approved, now awaiting HR" push
        # (or whatever a subject module's resolver supplies) — see
        # ApprovalService._notify_requester_of_advance.
        self.advanced_calls.append(
            {
                "requested_by_employee_id": requested_by_employee_id,
                "subject_summary": subject_summary,
                "message": message,
                "new_level": new_level,
                "approval_request_id": approval_request_id,
            }
        )


class FakeApprovalRequestRepository:
    def __init__(self):
        self._items: dict[uuid.UUID, object] = {}

    def get_by_id(self, entity_id):
        return self._items.get(entity_id)

    def create(self, entity):
        self._items[entity.id] = entity
        return entity

    def update(self, entity):
        self._items[entity.id] = entity
        return entity

    def delete(self, entity_id):
        self._items.pop(entity_id, None)

    def exists(self, entity_id):
        return entity_id in self._items

    def list(self, query):
        raise NotImplementedError

    def get_pending_by_subject(self, *, subject_type, subject_id):
        return next(
            (r for r in self._items.values() if r.subject_type == subject_type and r.subject_id == subject_id and r.status == ApprovalStatus.PENDING),
            None,
        )

    def list_by_subject(self, *, subject_type, subject_id):
        return [r for r in self._items.values() if r.subject_type == subject_type and r.subject_id == subject_id]


class FakeApprovalStepRepository:
    def __init__(self):
        self._items: dict[uuid.UUID, object] = {}

    def get_by_id(self, entity_id):
        return self._items.get(entity_id)

    def create(self, entity):
        self._items[entity.id] = entity
        return entity

    def update(self, entity):
        self._items[entity.id] = entity
        return entity

    def delete(self, entity_id):
        self._items.pop(entity_id, None)

    def exists(self, entity_id):
        return entity_id in self._items

    def list(self, query):
        raise NotImplementedError

    def get_by_request_and_level(self, *, approval_request_id, level):
        return next(
            (s for s in self._items.values() if s.approval_request_id == approval_request_id and s.level == level),
            None,
        )

    def list_by_request(self, *, approval_request_id):
        return sorted(
            (s for s in self._items.values() if s.approval_request_id == approval_request_id), key=lambda s: s.level
        )

    def list_pending_for_approver(self, *, approver_employee_id, held_permission_codes):
        result = []
        for s in self._items.values():
            if s.status != ApprovalStepStatus.PENDING:
                continue
            if s.approver_employee_id == approver_employee_id:
                result.append(s)
            elif s.approver_permission_code is not None and s.approver_permission_code in held_permission_codes:
                result.append(s)
        return result


class FakeAuthorizationPort:
    """Maps an employee id to the permission codes they hold — the fake
    counterpart of `apps.approvals.infrastructure.authorization_adapter
    .IdentityAuthorizationAdapter`, which does the same via a real
    cross-module call into Identity."""

    def __init__(self, permission_codes_by_employee: dict | None = None):
        self._by_employee = permission_codes_by_employee or {}

    def get_permission_codes_for_employee(self, employee_id):
        return self._by_employee.get(employee_id, frozenset())


class FakeSingleLevelChainResolver:
    """Level 1 = a fixed employee id; no level beyond that — mirrors
    apps.leave.infrastructure.leave_approval_chain_resolver.LeaveApprovalChainResolver's
    Phase 9 shape exactly."""

    def __init__(self, level_1_approver_id):
        self._approver = level_1_approver_id

    def resolve_next_approver(self, *, subject_type, subject_id, requested_by_employee_id, level):
        return ApproverAssignment.for_employee(self._approver) if level == 1 else None


class FakeTwoLevelChainResolver:
    """Simulates a HYPOTHETICAL two-level, both-employee-assigned subject
    module — proves ApprovalService supports dynamic levels with zero
    changes to itself, purely by how a resolver answers."""

    def __init__(self, level_1_approver_id, level_2_approver_id):
        self._level_1 = level_1_approver_id
        self._level_2 = level_2_approver_id

    def resolve_next_approver(self, *, subject_type, subject_id, requested_by_employee_id, level):
        if level == 1:
            return ApproverAssignment.for_employee(self._level_1)
        if level == 2:
            return ApproverAssignment.for_employee(self._level_2)
        return None


_TEST_ADVANCE_MESSAGE = "Your manager has approved your leave request. It is now awaiting HR processing."


class FakePermissionLevelChainResolver:
    """Level 1 = a fixed employee (the applicant's manager); level 2 = any
    employee holding a given permission code — mirrors Leave's real
    Phase 13 shape (`LeaveApprovalChainResolver`) exactly, including
    supplying a `requester_notification_message` for the level-2 assignment
    (Leave review round)."""

    def __init__(self, level_1_approver_id, level_2_permission_code):
        self._level_1 = level_1_approver_id
        self._level_2_permission = level_2_permission_code

    def resolve_next_approver(self, *, subject_type, subject_id, requested_by_employee_id, level):
        if level == 1:
            return ApproverAssignment.for_employee(self._level_1)
        if level == 2:
            return ApproverAssignment.for_permission(
                self._level_2_permission, requester_notification_message=_TEST_ADVANCE_MESSAGE
            )
        return None


class FakeNoApproverChainResolver:
    def resolve_next_approver(self, *, subject_type, subject_id, requested_by_employee_id, level):
        return None


class FakeChannelRestrictedSingleLevelChainResolver:
    """Level 1 = a fixed employee, restricted to one specific channel —
    the fake counterpart of Leave's real level-1 assignment
    (`ApprovalChannel.TELEGRAM`), but channel-agnostic itself so the same
    fake proves the engine's generic enforcement, not anything Leave-
    specific (Approval Workflow Changes review round)."""

    def __init__(self, level_1_approver_id, restricted_to_channel):
        self._approver = level_1_approver_id
        self._restricted_to_channel = restricted_to_channel

    def resolve_next_approver(self, *, subject_type, subject_id, requested_by_employee_id, level):
        if level != 1:
            return None
        return ApproverAssignment.for_employee(self._approver, restricted_to_channel=self._restricted_to_channel)


class FakeDualModeChainResolver:
    """Level 1 = dual-mode (Approval Workflow Changes v2): decidable by a
    specific employee via any channel except `permission_required_for_channel`,
    and by any holder of `permission_code` on that one channel instead —
    mirrors Leave's real level 1 shape exactly
    (`ApproverAssignment.for_employee_or_permission_by_channel`)."""

    def __init__(self, employee_id, permission_code, permission_required_for_channel):
        self._employee_id = employee_id
        self._permission_code = permission_code
        self._permission_required_for_channel = permission_required_for_channel

    def resolve_next_approver(self, *, subject_type, subject_id, requested_by_employee_id, level):
        if level != 1:
            return None
        return ApproverAssignment.for_employee_or_permission_by_channel(
            employee_id=self._employee_id,
            permission_code=self._permission_code,
            permission_required_for_channel=self._permission_required_for_channel,
        )


class FakeEmployeeLookupPort:
    """The fake counterpart of
    `apps.approvals.infrastructure.employee_lookup_adapter
    .EmployeeServiceLookupAdapter` — only `get_employee_display_info` is
    exercised by `ApprovalService` itself (the other three `EmployeeLookupPort`
    methods belong to `interface/views.py`'s caller-resolution helpers, never
    called by the service), so this fake only implements that one."""

    def __init__(self, display_info_by_employee: dict | None = None):
        self._by_employee = display_info_by_employee or {}

    def get_employee_display_info(self, employee_id):
        return self._by_employee.get(employee_id)

    def get_employee_id_by_user_id(self, user_id):
        raise NotImplementedError

    def get_employee_id_by_telegram_user_id(self, telegram_user_id):
        raise NotImplementedError

    def get_telegram_chat_id(self, employee_id):
        raise NotImplementedError


def _build(
    resolver=None, authorization=None, employee_lookup=None
) -> tuple[ApprovalService, FakeApprovalRequestRepository, FakeApprovalStepRepository, FakeNotificationPort, FakeEventBus]:
    requests_repo = FakeApprovalRequestRepository()
    steps_repo = FakeApprovalStepRepository()
    notifications = FakeNotificationPort()
    event_bus = FakeEventBus()
    registry = ApprovalChainResolverRegistry()
    if resolver is not None:
        registry.register(_SUBJECT_TYPE, resolver)
    service = ApprovalService(
        approval_request_repository=requests_repo,
        approval_step_repository=steps_repo,
        chain_resolvers=registry,
        notifications=notifications,
        authorization=authorization if authorization is not None else FakeAuthorizationPort(),
        employee_lookup=employee_lookup if employee_lookup is not None else FakeEmployeeLookupPort(),
        unit_of_work=FakeUnitOfWork(),
        event_bus=event_bus,
    )
    return service, requests_repo, steps_repo, notifications, event_bus


# --- create_approval_request ----------------------------------------------


def test_create_approval_request_opens_level_1_and_notifies_approver() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, requests_repo, steps_repo, notifications, event_bus = _build(FakeSingleLevelChainResolver(approver_id))

    result = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="Annual Leave: 3 days",
        )
    )

    assert result.status == "pending"
    assert result.current_level == 1
    assert len(result.steps) == 1
    assert result.steps[0].approver_employee_id == approver_id
    assert len(notifications.requested_calls) == 1
    assert notifications.requested_calls[0]["approver_employee_id"] == approver_id
    assert any(type(e).__name__ == "ApprovalRequested" for e in event_bus.published)


def test_create_approval_request_raises_when_no_resolver_registered() -> None:
    service, *_ = _build(resolver=None)

    with pytest.raises(NoApprovalChainResolverRegisteredError):
        service.create_approval_request(
            CreateApprovalRequestRequest(
                subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=uuid.uuid4(),
                subject_summary="x",
            )
        )


def test_create_approval_request_raises_when_no_approver_available() -> None:
    service, *_ = _build(FakeNoApproverChainResolver())

    with pytest.raises(NoApproverAvailableError):
        service.create_approval_request(
            CreateApprovalRequestRequest(
                subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=uuid.uuid4(),
                subject_summary="x",
            )
        )


# --- cancel_for_subject (round 17 item 2) ----------------------------------


def test_cancel_for_subject_marks_request_and_current_step_cancelled() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, requests_repo, steps_repo, notifications, event_bus = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    result = service.cancel_for_subject(
        CancelApprovalRequestForSubjectRequest(subject_type=_SUBJECT_TYPE, subject_id=subject_id, reason="Plans changed")
    )

    assert result is not None
    assert result.status == "cancelled"
    assert result.steps[0].status == "cancelled"
    assert result.steps[0].comments == "Plans changed"
    # Nobody "decided" this step — it was closed by the subject module, not
    # an approver's own choice — distinct from approve()/reject()'s always-set
    # decided_by_employee_id.
    assert result.steps[0].decided_by_employee_id is None
    assert any(type(e).__name__ == "ApprovalRequestCancelled" for e in event_bus.published)
    # No decision notification fires for a cancellation — that channel is
    # reserved for an actual approve/reject decision (`notify_decision_made`).
    assert len(notifications.decided_calls) == 0


def test_cancel_for_subject_is_a_noop_when_nothing_is_pending() -> None:
    """No approval request was ever created for this subject — idempotent
    no-op, not an error, matching `cancel_leave`'s "always call this,
    regardless of prior state" usage."""
    service, *_ = _build(FakeSingleLevelChainResolver(uuid.uuid4()))

    result = service.cancel_for_subject(
        CancelApprovalRequestForSubjectRequest(subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4())
    )

    assert result is None


def test_cancel_for_subject_is_a_noop_once_already_fully_approved() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.decide(
        DecideApprovalRequest(approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE, channel=_WEB)
    )

    result = service.cancel_for_subject(
        CancelApprovalRequestForSubjectRequest(subject_type=_SUBJECT_TYPE, subject_id=subject_id)
    )

    assert result is None
    # The already-approved request/step must be left untouched.
    detail = service.get_detail(created.id)
    assert detail.status == "approved"
    assert detail.steps[0].status == "approved"


def test_decide_raises_once_the_approval_request_was_cancelled() -> None:
    """Round 17 item 2's core requirement: once cancelled, no pending
    approval may be approved or rejected — enforced entirely by `decide()`'s
    EXISTING `status != PENDING` guard, with zero changes to `decide()`
    itself."""
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.cancel_for_subject(
        CancelApprovalRequestForSubjectRequest(subject_type=_SUBJECT_TYPE, subject_id=subject_id)
    )

    with pytest.raises(ApprovalRequestNotPendingError):
        service.decide(
            DecideApprovalRequest(
                approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE, channel=_WEB
            )
        )


def test_cancelled_step_no_longer_appears_in_the_approvers_pending_list() -> None:
    """A cancelled request's step must drop out of `list_pending_for_approver`
    too, not just fail `decide()` — otherwise an approver would keep seeing
    a phantom entry they can no longer act on."""
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id))
    service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    service.cancel_for_subject(
        CancelApprovalRequestForSubjectRequest(subject_type=_SUBJECT_TYPE, subject_id=subject_id)
    )

    assert service.list_pending_for_approver(approver_id) == []


# --- decide: single-level (Leave's actual shape) --------------------------


def test_decide_approve_single_level_marks_request_approved_and_notifies_requester() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, requests_repo, steps_repo, notifications, event_bus = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="Annual Leave: 3 days",
        )
    )

    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE, channel=_WEB, comments="OK"
        )
    )

    assert result.status == "approved"
    assert result.steps[0].status == "approved"
    assert result.steps[0].comments == "OK"
    assert len(notifications.decided_calls) == 1
    assert notifications.decided_calls[0]["final_status"] == "approved"
    assert any(type(e).__name__ == "ApprovalDecided" for e in event_bus.published)


def test_decide_reject_single_level_marks_request_rejected() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_REJECT, channel=_WEB,
            comments="Not enough coverage",
        )
    )

    assert result.status == "rejected"
    assert result.steps[0].status == "rejected"


def test_decide_raises_when_acting_employee_is_not_the_assigned_approver() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    with pytest.raises(NotTheAssignedApproverError):
        service.decide(
            DecideApprovalRequest(
                approval_request_id=created.id, acting_employee_id=uuid.uuid4(), decision=DECISION_APPROVE, channel=_WEB
            )
        )


def test_decide_raises_when_request_already_decided() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.decide(
        DecideApprovalRequest(approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE, channel=_WEB)
    )

    with pytest.raises(ApprovalRequestNotPendingError):
        service.decide(
            DecideApprovalRequest(
                approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE, channel=_WEB
            )
        )


def test_decide_raises_not_found_for_unknown_request() -> None:
    service, *_ = _build(FakeSingleLevelChainResolver(uuid.uuid4()))

    with pytest.raises(ApprovalRequestNotFoundError):
        service.decide(
            DecideApprovalRequest(approval_request_id=uuid.uuid4(), acting_employee_id=uuid.uuid4(), decision=DECISION_APPROVE, channel=_WEB)
        )


# --- decide: dynamic multi-level (the core architectural requirement) -----


def test_decide_approve_advances_to_a_dynamically_resolved_second_level() -> None:
    """Proves multi-level support requires ZERO changes to ApprovalService
    — only a resolver that happens to answer a second level."""
    level_1_approver, level_2_approver, requester_id, subject_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    service, requests_repo, steps_repo, notifications, event_bus = _build(
        FakeTwoLevelChainResolver(level_1_approver, level_2_approver)
    )
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=level_1_approver, decision=DECISION_APPROVE, channel=_WEB
        )
    )

    assert result.status == "pending"  # NOT approved yet — level 2 still pending
    assert result.current_level == 2
    assert len(result.steps) == 2
    assert result.steps[1].approver_employee_id == level_2_approver
    assert result.steps[1].status == "pending"
    # Level 1's approval must not have triggered a "decided" notification —
    # only a second "requested" notification, to the level-2 approver.
    assert len(notifications.decided_calls) == 0
    assert len(notifications.requested_calls) == 2
    assert notifications.requested_calls[1]["approver_employee_id"] == level_2_approver
    # Leave review round: the ORIGINAL REQUESTER also gets told the chain
    # advanced (distinct from the level-2 approver's own "requested" push
    # above) — falls back to a generic message since this fake resolver
    # never supplies `requester_notification_message`.
    assert len(notifications.advanced_calls) == 1
    assert notifications.advanced_calls[0]["requested_by_employee_id"] == requester_id
    assert notifications.advanced_calls[0]["new_level"] == 2
    assert "level 2" in notifications.advanced_calls[0]["message"]

    # Level 2 approving is what finally concludes the whole request.
    final = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=level_2_approver, decision=DECISION_APPROVE, channel=_WEB
        )
    )
    assert final.status == "approved"
    assert len(notifications.decided_calls) == 1


def test_decide_reject_at_second_level_ends_the_whole_request() -> None:
    level_1_approver, level_2_approver, requester_id, subject_id = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    service, *_ = _build(FakeTwoLevelChainResolver(level_1_approver, level_2_approver))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.decide(
        DecideApprovalRequest(approval_request_id=created.id, acting_employee_id=level_1_approver, decision=DECISION_APPROVE, channel=_WEB)
    )

    final = service.decide(
        DecideApprovalRequest(approval_request_id=created.id, acting_employee_id=level_2_approver, decision=DECISION_REJECT, channel=_WEB)
    )

    assert final.status == "rejected"


# --- reads -----------------------------------------------------------------


def test_list_pending_for_approver_returns_only_that_approvers_pending_steps() -> None:
    approver_a, approver_b = uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_a))
    service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=uuid.uuid4(), requested_by_employee_id=uuid.uuid4(), subject_summary="a"
        )
    )

    pending_for_a = service.list_pending_for_approver(approver_a)
    pending_for_b = service.list_pending_for_approver(approver_b)

    assert len(pending_for_a) == 1
    assert pending_for_b == []


def test_get_detail_raises_not_found_for_unknown_request() -> None:
    service, *_ = _build(FakeSingleLevelChainResolver(uuid.uuid4()))

    with pytest.raises(ApprovalRequestNotFoundError):
        service.get_detail(uuid.uuid4())


# --- decide: permission-based levels (Phase 13 — Leave's HR/Admin level) ---


def test_decide_approve_advances_to_a_permission_based_second_level() -> None:
    """Mirrors Leave's real shape: level 1 is the manager (employee-
    assigned), level 2 is "anyone holding leave.manage_leave" (permission-
    assigned). No single employee id exists for level 2, so no
    "requested" push should fire for it — the qualifying employees find it
    via list_pending_for_approver instead (see the test below)."""
    level_1_approver, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    permission_code = "leave.manage_leave"
    service, requests_repo, steps_repo, notifications, event_bus = _build(
        FakePermissionLevelChainResolver(level_1_approver, permission_code)
    )
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=level_1_approver, decision=DECISION_APPROVE, channel=_WEB
        )
    )

    assert result.status == "pending"  # NOT approved yet — level 2 still pending
    assert result.current_level == 2
    assert result.steps[1].approver_employee_id is None
    assert result.steps[1].approver_permission_code == permission_code
    # Only level 1's own "requested" push fired — level 2 has no single
    # employee to address, so no second push.
    assert len(notifications.requested_calls) == 1
    assert len(notifications.decided_calls) == 0
    # Leave review round: the applicant IS still told — with the exact
    # subject-supplied wording, not a generic fallback — that their manager
    # approved and the request is now awaiting HR.
    assert len(notifications.advanced_calls) == 1
    assert notifications.advanced_calls[0]["requested_by_employee_id"] == requester_id
    assert notifications.advanced_calls[0]["message"] == _TEST_ADVANCE_MESSAGE


def test_decide_permission_based_step_accepts_any_qualifying_employee() -> None:
    """Two different employees both hold leave.manage_leave — either one
    (not just one designated person) can decide the HR-level step, and
    ApprovalDecided.decided_by_employee_id reflects whoever actually
    acted, not some fixed "assigned" employee (there isn't one)."""
    level_1_approver, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    hr_admin_one, hr_admin_two = uuid.uuid4(), uuid.uuid4()
    permission_code = "leave.manage_leave"
    authz = FakeAuthorizationPort(
        {hr_admin_one: frozenset({permission_code}), hr_admin_two: frozenset({permission_code})}
    )
    service, requests_repo, steps_repo, notifications, event_bus = _build(
        FakePermissionLevelChainResolver(level_1_approver, permission_code), authorization=authz
    )
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=level_1_approver, decision=DECISION_APPROVE, channel=_WEB
        )
    )

    final = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=hr_admin_two, decision=DECISION_APPROVE, channel=_WEB, comments="ok"
        )
    )

    assert final.status == "approved"
    assert len(notifications.decided_calls) == 1
    decided_events = [e for e in event_bus.published if type(e).__name__ == "ApprovalDecided"]
    assert len(decided_events) == 1
    assert decided_events[0].decided_by_employee_id == hr_admin_two


def test_decide_permission_based_step_rejects_an_employee_without_the_permission() -> None:
    level_1_approver, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    unrelated_employee = uuid.uuid4()
    permission_code = "leave.manage_leave"
    service, *_ = _build(FakePermissionLevelChainResolver(level_1_approver, permission_code))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=level_1_approver, decision=DECISION_APPROVE, channel=_WEB
        )
    )

    with pytest.raises(NotTheAssignedApproverError):
        service.decide(
            DecideApprovalRequest(
                approval_request_id=created.id, acting_employee_id=unrelated_employee, decision=DECISION_APPROVE, channel=_WEB
            )
        )


def test_list_pending_for_approver_includes_permission_based_steps_the_caller_qualifies_for() -> None:
    level_1_approver, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    hr_admin, unrelated_employee = uuid.uuid4(), uuid.uuid4()
    permission_code = "leave.manage_leave"
    authz = FakeAuthorizationPort({hr_admin: frozenset({permission_code})})
    service, *_ = _build(FakePermissionLevelChainResolver(level_1_approver, permission_code), authorization=authz)
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=level_1_approver, decision=DECISION_APPROVE, channel=_WEB
        )
    )

    pending_for_hr_admin = service.list_pending_for_approver(hr_admin)
    pending_for_unrelated = service.list_pending_for_approver(unrelated_employee)

    assert len(pending_for_hr_admin) == 1
    assert pending_for_hr_admin[0].steps[0].approver_permission_code == permission_code
    assert pending_for_unrelated == []


# --- decide/list: channel restriction (Approval Workflow Changes review) ---


def test_decide_rejects_when_the_callers_channel_does_not_match_the_steps_restriction() -> None:
    """Generic proof, independent of Leave: a step whose assignment
    restricted it to one channel cannot be decided from another — even by
    the exact right, correctly-assigned employee. Checked before (and
    instead of) `NotTheAssignedApproverError` — the wrong channel is
    rejected on its own terms."""
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeChannelRestrictedSingleLevelChainResolver(approver_id, _TELEGRAM))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    assert created.steps[0].restricted_to_channel == _TELEGRAM

    with pytest.raises(ApprovalChannelNotAllowedError):
        service.decide(
            DecideApprovalRequest(
                approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE,
                channel=_WEB,
            )
        )


def test_decide_succeeds_when_the_callers_channel_matches_the_steps_restriction() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeChannelRestrictedSingleLevelChainResolver(approver_id, _TELEGRAM))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE,
            channel=_TELEGRAM,
        )
    )

    assert result.status == "approved"


def test_decide_with_no_restriction_accepts_any_channel() -> None:
    """`restricted_to_channel=None` (the default every assignment had before
    this field existed) must keep behaving exactly as before — decidable
    from either channel."""
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id))
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    assert created.steps[0].restricted_to_channel is None

    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=approver_id, decision=DECISION_APPROVE,
            channel=_TELEGRAM,
        )
    )

    assert result.status == "approved"


def test_list_pending_for_approver_excludes_a_step_restricted_to_a_different_channel() -> None:
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeChannelRestrictedSingleLevelChainResolver(approver_id, _TELEGRAM))
    service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    pending_via_web = service.list_pending_for_approver(approver_id, channel=_WEB)
    pending_via_telegram = service.list_pending_for_approver(approver_id, channel=_TELEGRAM)
    pending_unfiltered = service.list_pending_for_approver(approver_id)

    assert pending_via_web == []
    assert len(pending_via_telegram) == 1
    assert len(pending_unfiltered) == 1


# --- decide/list: dual-mode approver (Approval Workflow Changes v2) --------

_LEVEL1_PERMISSION = "approvals.level1_approve"


def test_decide_dual_mode_web_requires_the_permission_not_identity() -> None:
    """The web channel is governed purely by holding the permission code —
    being the originally-referenced employee (the manager) is neither
    necessary nor sufficient on that one channel."""
    manager_id, permission_holder_id, requester_id, subject_id = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
    )
    authz = FakeAuthorizationPort({permission_holder_id: frozenset({_LEVEL1_PERMISSION})})
    service, *_ = _build(FakeDualModeChainResolver(manager_id, _LEVEL1_PERMISSION, _WEB), authorization=authz)
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    # The manager, WITHOUT the permission, cannot decide via web.
    with pytest.raises(NotTheAssignedApproverError):
        service.decide(
            DecideApprovalRequest(
                approval_request_id=created.id, acting_employee_id=manager_id, decision=DECISION_APPROVE, channel=_WEB
            )
        )

    # A different employee who DOES hold the permission can, even though
    # they are not the manager.
    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=permission_holder_id, decision=DECISION_APPROVE,
            channel=_WEB,
        )
    )
    assert result.status == "approved"


def test_decide_dual_mode_telegram_requires_identity_not_permission() -> None:
    """Telegram is governed purely by being the assigned employee — holding
    the permission is neither necessary nor sufficient there."""
    manager_id, permission_holder_id, requester_id, subject_id = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
    )
    authz = FakeAuthorizationPort({permission_holder_id: frozenset({_LEVEL1_PERMISSION})})
    service, *_ = _build(FakeDualModeChainResolver(manager_id, _LEVEL1_PERMISSION, _WEB), authorization=authz)
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    # The permission holder, NOT being the manager, cannot decide via Telegram.
    with pytest.raises(NotTheAssignedApproverError):
        service.decide(
            DecideApprovalRequest(
                approval_request_id=created.id, acting_employee_id=permission_holder_id, decision=DECISION_APPROVE,
                channel=_TELEGRAM,
            )
        )

    # The manager (who doesn't hold the permission here) CAN still decide
    # via Telegram — identity alone governs that channel.
    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=manager_id, decision=DECISION_APPROVE,
            channel=_TELEGRAM,
        )
    )
    assert result.status == "approved"


def test_list_pending_for_approver_dual_mode_web_excludes_manager_without_permission() -> None:
    manager_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    service, *_ = _build(FakeDualModeChainResolver(manager_id, _LEVEL1_PERMISSION, _WEB))
    service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    pending_web = service.list_pending_for_approver(manager_id, channel=_WEB)
    pending_telegram = service.list_pending_for_approver(manager_id, channel=_TELEGRAM)

    assert pending_web == []  # manager doesn't hold approvals.level1_approve here
    assert len(pending_telegram) == 1  # still decidable via Telegram, by identity


def test_list_pending_for_approver_dual_mode_web_includes_non_manager_permission_holder() -> None:
    manager_id, permission_holder_id, requester_id, subject_id = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
    )
    authz = FakeAuthorizationPort({permission_holder_id: frozenset({_LEVEL1_PERMISSION})})
    service, *_ = _build(FakeDualModeChainResolver(manager_id, _LEVEL1_PERMISSION, _WEB), authorization=authz)
    service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    pending_web = service.list_pending_for_approver(permission_holder_id, channel=_WEB)
    pending_telegram = service.list_pending_for_approver(permission_holder_id, channel=_TELEGRAM)

    assert len(pending_web) == 1
    assert pending_telegram == []  # not the manager, so identity check fails on Telegram


def test_decided_by_employee_id_and_enrichment_reflect_the_actual_decider() -> None:
    """A dual-mode step decided by someone other than the originally-
    referenced employee must show THAT person's name, not the reference
    employee's — this is what makes "approved by X" correct once level 1
    can be decided by any approvals.level1_approve holder, not just the
    manager."""
    manager_id, permission_holder_id, requester_id, subject_id = (
        uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
    )
    authz = FakeAuthorizationPort({permission_holder_id: frozenset({_LEVEL1_PERMISSION})})
    employee_lookup = FakeEmployeeLookupPort(
        {manager_id: ("Manager Name", "EMP-MGR"), permission_holder_id: ("Backup Approver", "EMP-BKP")}
    )
    service, *_ = _build(
        FakeDualModeChainResolver(manager_id, _LEVEL1_PERMISSION, _WEB),
        authorization=authz,
        employee_lookup=employee_lookup,
    )
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    # While pending, shows the referenced manager — the "who's assigned" reference.
    assert created.steps[0].approver_employee_name == "Manager Name"

    result = service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=permission_holder_id, decision=DECISION_APPROVE,
            channel=_WEB,
        )
    )

    # Once decided by someone else, the DECIDER's name/code is shown instead.
    assert result.steps[0].approver_employee_name == "Backup Approver"
    assert result.steps[0].approver_employee_code == "EMP-BKP"


# --- read enrichment: approver display name/code (Approval Workflow Changes) -


def test_get_detail_enriches_a_for_employee_steps_approver_name_and_code() -> None:
    """Generic proof: any `for_employee` step's response carries the
    approver's display name/code, resolved via `EmployeeLookupPort` — this
    engine never learns the approver is "a manager," it just always shows
    who a single-employee assignment names."""
    approver_id, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    employee_lookup = FakeEmployeeLookupPort({approver_id: ("Jane Doe", "EMP-0042")})
    service, *_ = _build(FakeSingleLevelChainResolver(approver_id), employee_lookup=employee_lookup)
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )

    result = service.get_detail(created.id)

    assert result.steps[0].approver_employee_name == "Jane Doe"
    assert result.steps[0].approver_employee_code == "EMP-0042"


def test_get_detail_leaves_a_permission_based_steps_approver_name_and_code_null() -> None:
    """There is no single employee to name for a permission-based step —
    enrichment must be a no-op, not an error or a guess."""
    level_1_approver, requester_id, subject_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    permission_code = "leave.manage_leave"
    # Deliberately configured to return something for ANY id, proving the
    # service never even calls it for a permission-based step (there is no
    # approver_employee_id to look up).
    employee_lookup = FakeEmployeeLookupPort({level_1_approver: ("Should Not Appear", "EMP-0000")})
    service, *_ = _build(
        FakePermissionLevelChainResolver(level_1_approver, permission_code), employee_lookup=employee_lookup
    )
    created = service.create_approval_request(
        CreateApprovalRequestRequest(
            subject_type=_SUBJECT_TYPE, subject_id=subject_id, requested_by_employee_id=requester_id,
            subject_summary="x",
        )
    )
    service.decide(
        DecideApprovalRequest(
            approval_request_id=created.id, acting_employee_id=level_1_approver, decision=DECISION_APPROVE,
            channel=_WEB,
        )
    )

    result = service.get_detail(created.id)

    assert result.steps[1].approver_permission_code == permission_code
    assert result.steps[1].approver_employee_name is None
    assert result.steps[1].approver_employee_code is None
