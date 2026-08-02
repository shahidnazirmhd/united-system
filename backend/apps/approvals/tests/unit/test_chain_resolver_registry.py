"""Unit tests for `ApprovalChainResolverRegistry` — a plain in-memory
mapping, tested in isolation from `ApprovalService` itself."""
from __future__ import annotations

import uuid

from apps.approvals.application.registry import ApprovalChainResolverRegistry


class _FakeResolver:
    def resolve_next_approver(self, *, subject_type, subject_id, requested_by_employee_id, level):
        return None


def test_get_returns_none_for_unregistered_subject_type() -> None:
    registry = ApprovalChainResolverRegistry()

    assert registry.get("leave.leave_request") is None


def test_register_then_get_returns_the_same_resolver_instance() -> None:
    registry = ApprovalChainResolverRegistry()
    resolver = _FakeResolver()

    registry.register("leave.leave_request", resolver)

    assert registry.get("leave.leave_request") is resolver


def test_register_overwrites_a_previous_resolver_for_the_same_subject_type() -> None:
    registry = ApprovalChainResolverRegistry()
    first, second = _FakeResolver(), _FakeResolver()

    registry.register("leave.leave_request", first)
    registry.register("leave.leave_request", second)

    assert registry.get("leave.leave_request") is second


def test_distinct_subject_types_are_independent() -> None:
    registry = ApprovalChainResolverRegistry()
    leave_resolver, attendance_resolver = _FakeResolver(), _FakeResolver()

    registry.register("leave.leave_request", leave_resolver)
    registry.register("attendance.correction_request", attendance_resolver)

    assert registry.get("leave.leave_request") is leave_resolver
    assert registry.get("attendance.correction_request") is attendance_resolver
