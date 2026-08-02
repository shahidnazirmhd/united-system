"""Unit tests for `LeaveRequestService.get_statistics` (Phase 14: Dashboard)
— hand-rolled fakes, no Django, no database.

Every collaborator `LeaveRequestService.__init__` requires but
`get_statistics` never touches (validation/balance services, unit of work,
event bus, approval/settings/holiday/employee-status/notification ports)
is stood in for by `_Unused`, a stub that raises if any of its attributes
are actually called — keeping this file honest that `get_statistics` only
reaches into `leave_request_repository` and `leave_type_repository`.
"""
from __future__ import annotations

import uuid
from datetime import date

from apps.leave.application.services.leave_request_service import LeaveRequestService
from apps.leave.domain.entities import LeaveType
from apps.leave.domain.repositories import LeaveStatisticsSnapshot


class _Unused:
    """Stands in for every constructor dependency `get_statistics` never
    calls — any attribute access returns a callable that raises, so an
    accidental dependency on one of these would fail loudly, not silently
    return `None`."""

    def __getattr__(self, name):
        def _raise(*args, **kwargs):
            raise AssertionError(f"get_statistics() should not call `{name}`")

        return _raise


class FakeLeaveRequestStatisticsRepository(_Unused):
    def __init__(self, snapshot: LeaveStatisticsSnapshot, *, on_leave_today: frozenset | None = None):
        self._snapshot = snapshot
        self._on_leave_today = on_leave_today or frozenset()

    def get_statistics_snapshot(self, *, monthly_trend_since: date) -> LeaveStatisticsSnapshot:
        return self._snapshot

    def list_employee_ids_with_approved_leave_covering(self, target_date: date) -> frozenset:
        return self._on_leave_today


class FakeLeaveTypeRepository(_Unused):
    def __init__(self, leave_types: dict):
        self._leave_types = leave_types

    def get_by_id(self, leave_type_id):
        return self._leave_types.get(leave_type_id)


def _build_service(
    *, snapshot: LeaveStatisticsSnapshot, leave_types: dict | None = None, on_leave_today: frozenset | None = None
) -> LeaveRequestService:
    return LeaveRequestService(
        leave_request_repository=FakeLeaveRequestStatisticsRepository(snapshot, on_leave_today=on_leave_today),
        leave_type_repository=FakeLeaveTypeRepository(leave_types or {}),
        validation_service=_Unused(),
        balance_service=_Unused(),
        unit_of_work=_Unused(),
        event_bus=_Unused(),
        approval_requests=_Unused(),
        settings_lookup=_Unused(),
        holiday_lookup=_Unused(),
        employee_status=_Unused(),
        notifications=_Unused(),
    )


def test_get_statistics_reports_status_and_on_leave_today_counts() -> None:
    employee_id = uuid.uuid4()
    snapshot = LeaveStatisticsSnapshot(by_status={"approved": 5, "pending": 2})
    service = _build_service(snapshot=snapshot, on_leave_today=frozenset({employee_id}))

    result = service.get_statistics()

    assert result.status_breakdown == {"approved": 5, "pending": 2}
    assert result.on_leave_today_count == 1


def test_get_statistics_resolves_leave_type_names_and_falls_back_for_unknown() -> None:
    known_id = uuid.uuid4()
    unknown_id = uuid.uuid4()
    leave_type = LeaveType(id=known_id, name="Sick Leave", code="SICK")
    snapshot = LeaveStatisticsSnapshot(by_leave_type=[(known_id, 4), (unknown_id, 1)])
    service = _build_service(snapshot=snapshot, leave_types={known_id: leave_type})

    result = service.get_statistics()

    by_id = {stat.leave_type_id: stat for stat in result.leave_type_breakdown}
    assert by_id[known_id].leave_type_name == "Sick Leave"
    assert by_id[known_id].count == 4
    assert by_id[unknown_id].leave_type_name == "Unknown"


def test_get_statistics_backfills_zero_count_months_for_a_gapless_trend() -> None:
    """Regression guard: `_month_sequence` must produce every month in the
    trailing window even when the snapshot only reports months that had at
    least one application — see `LeaveStatisticsSnapshot.monthly_trend`'s
    own docstring for why a gap would otherwise reach a line/area chart."""
    today = date.today()
    snapshot = LeaveStatisticsSnapshot(monthly_trend=[(f"{today.year:04d}-{today.month:02d}", 3)])
    service = _build_service(snapshot=snapshot)

    result = service.get_statistics(monthly_trend_months=6)

    assert len(result.monthly_trend) == 7  # 6 months back through the current month, inclusive
    counts = {stat.month: stat.count for stat in result.monthly_trend}
    assert counts[f"{today.year:04d}-{today.month:02d}"] == 3
    assert sum(1 for count in counts.values() if count == 0) == 6
