"""Unit tests for api_client/endpoints/approvals.py — the wire-shape
parsing layer for apps.approvals's Telegram-facing REST endpoints.
Mirrors tests/unit/test_leave_application.py's discipline of faking only
the HRMSClient boundary."""
from __future__ import annotations

from dataclasses import dataclass, field

from src.api_client.endpoints.approvals import ApprovalsEndpoint


@dataclass
class _FakeHRMSClient:
    get_response: object = None
    post_response: object = None
    get_calls: list = field(default_factory=list)
    post_calls: list = field(default_factory=list)

    async def get(self, path, *, params=None):
        self.get_calls.append({"path": path, "params": params})
        return self.get_response

    async def post(self, path, *, json_body=None):
        self.post_calls.append({"path": path, "json_body": json_body})
        return self.post_response


_RAW_STEP = {
    "id": "step-1",
    "approval_request_id": "req-1",
    "level": 1,
    "approver_employee_id": "mgr-1",
    "status": "pending",
    "comments": None,
    "decided_at": None,
}

_RAW_REQUEST = {
    "id": "req-1",
    "subject_type": "leave.leave_request",
    "subject_id": "leave-req-1",
    "requested_by_employee_id": "emp-1",
    "subject_summary": "Annual Leave: 3 days",
    "status": "pending",
    "current_level": 1,
    "steps": [_RAW_STEP],
}


async def test_list_pending_parses_every_item_and_sends_telegram_user_id():
    client = _FakeHRMSClient(get_response=[_RAW_REQUEST])
    endpoint = ApprovalsEndpoint(client)

    result = await endpoint.list_pending(telegram_user_id=42)

    assert len(result) == 1
    assert result[0].id == "req-1"
    assert result[0].steps[0].approver_employee_id == "mgr-1"
    assert client.get_calls[0]["params"] == {"telegram_user_id": 42}


async def test_decide_sends_all_fields_and_parses_result():
    client = _FakeHRMSClient(post_response=_RAW_REQUEST)
    endpoint = ApprovalsEndpoint(client)

    result = await endpoint.decide(
        telegram_user_id=42, approval_request_id="req-1", decision="approve", comments="OK"
    )

    assert result.status == "pending"
    sent = client.post_calls[0]["json_body"]
    assert sent == {
        "telegram_user_id": 42,
        "approval_request_id": "req-1",
        "decision": "approve",
        "comments": "OK",
    }
