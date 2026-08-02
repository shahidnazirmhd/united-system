"""One file per backend module the Gateway calls — this one talks only to
`apps/approvals`'s Telegram-facing endpoints (`/api/v1/approvals/telegram/*`),
mirroring `api_client/endpoints/leave.py`'s module boundary exactly
(HRMS_Folder_Structure.md section 3.3).

Every amount/date field is kept as the backend's own string representation
where one exists — same "this file only deserializes, never interprets"
discipline as `api_client/endpoints/leave.py`'s docstring, applied here too.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api_client.hrms_client import HRMSClient


@dataclass(frozen=True)
class ApprovalStep:
    id: str
    approval_request_id: str
    level: int
    approver_employee_id: str
    status: str
    comments: str | None
    decided_at: str | None


@dataclass(frozen=True)
class ApprovalRequest:
    id: str
    subject_type: str
    subject_id: str
    requested_by_employee_id: str
    subject_summary: str
    status: str
    current_level: int
    steps: list[ApprovalStep] = field(default_factory=list)


def _parse_step(data: dict) -> ApprovalStep:
    return ApprovalStep(
        id=data["id"],
        approval_request_id=data["approval_request_id"],
        level=data["level"],
        approver_employee_id=data["approver_employee_id"],
        status=data["status"],
        comments=data.get("comments"),
        decided_at=data.get("decided_at"),
    )


def _parse_request(data: dict) -> ApprovalRequest:
    return ApprovalRequest(
        id=data["id"],
        subject_type=data["subject_type"],
        subject_id=data["subject_id"],
        requested_by_employee_id=data["requested_by_employee_id"],
        subject_summary=data["subject_summary"],
        status=data["status"],
        current_level=data["current_level"],
        steps=[_parse_step(s) for s in data.get("steps", [])],
    )


class ApprovalsEndpoint:
    def __init__(self, hrms_client: HRMSClient) -> None:
        self._client = hrms_client

    async def list_pending(self, *, telegram_user_id: int) -> list[ApprovalRequest]:
        data = await self._client.get(
            "/api/v1/approvals/telegram/pending/", params={"telegram_user_id": telegram_user_id}
        )
        return [_parse_request(item) for item in data]

    async def decide(
        self,
        *,
        telegram_user_id: int,
        approval_request_id: str,
        decision: str,
        comments: str | None,
    ) -> ApprovalRequest:
        data = await self._client.post(
            "/api/v1/approvals/telegram/decide/",
            json_body={
                "telegram_user_id": telegram_user_id,
                "approval_request_id": approval_request_id,
                "decision": decision,
                "comments": comments,
            },
        )
        return _parse_request(data)
