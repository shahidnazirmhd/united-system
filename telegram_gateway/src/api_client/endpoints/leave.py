"""One file per backend module the Gateway calls — this one talks only to
`apps/leave`'s Telegram-facing endpoints (`/api/v1/leave/telegram/*`),
mirroring `api_client/endpoints/employees.py`'s module boundary exactly
(HRMS_Folder_Structure.md section 3.3). Every method here maps 1:1 to one
of the Gateway-facing views at `apps/leave/interface/views.py`.

Every amount/date field is kept as the backend's own string representation
(`"20.00"`, `"2026-09-01"`) rather than parsed into `Decimal`/`date` here —
this file's only job is deserializing the wire shape, never interpreting
it; `formatting/leave_formatter.py` decides how to display these strings,
and no arithmetic on them happens anywhere in this service (the backend is
the sole source of truth for leave balance math, matching "no business
logic in Telegram Gateway" the same way "no business logic in Django Views"
applies to the backend's own interface layer).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type hint only — see api_client/hrms_client.py's identical note.
    from src.api_client.hrms_client import HRMSClient


@dataclass(frozen=True)
class LeaveType:
    id: str
    name: str
    code: str
    default_annual_days: str
    is_paid: bool
    requires_approval: bool
    is_active: bool


@dataclass(frozen=True)
class LeaveBalance:
    employee_id: str
    leave_type_id: str
    leave_type_name: str | None
    year: int
    entitled_days: str
    used_days: str
    carried_forward_days: str
    available_days: str
    pending_days: str


@dataclass(frozen=True)
class LeaveRequest:
    id: str
    employee_id: str
    leave_type_id: str
    leave_type_name: str | None
    start_date: str
    end_date: str
    total_days: str
    reason: str | None
    status: str
    approved_by: str | None
    decided_at: str | None
    decision_comments: str | None
    cancelled_at: str | None
    cancellation_reason: str | None


@dataclass(frozen=True)
class LeaveHistoryPage:
    items: list[LeaveRequest]
    page: int
    page_size: int
    total_count: int
    total_pages: int


def _parse_leave_type(data: dict) -> LeaveType:
    return LeaveType(
        id=data["id"],
        name=data["name"],
        code=data["code"],
        default_annual_days=data["default_annual_days"],
        is_paid=data["is_paid"],
        requires_approval=data["requires_approval"],
        is_active=data["is_active"],
    )


def _parse_leave_balance(data: dict) -> LeaveBalance:
    return LeaveBalance(
        employee_id=data["employee_id"],
        leave_type_id=data["leave_type_id"],
        leave_type_name=data.get("leave_type_name"),
        year=data["year"],
        entitled_days=data["entitled_days"],
        used_days=data["used_days"],
        carried_forward_days=data["carried_forward_days"],
        available_days=data["available_days"],
        pending_days=data["pending_days"],
    )


def _parse_leave_request(data: dict) -> LeaveRequest:
    return LeaveRequest(
        id=data["id"],
        employee_id=data["employee_id"],
        leave_type_id=data["leave_type_id"],
        leave_type_name=data.get("leave_type_name"),
        start_date=data["start_date"],
        end_date=data["end_date"],
        total_days=data["total_days"],
        reason=data.get("reason"),
        status=data["status"],
        approved_by=data.get("approved_by"),
        decided_at=data.get("decided_at"),
        decision_comments=data.get("decision_comments"),
        cancelled_at=data.get("cancelled_at"),
        cancellation_reason=data.get("cancellation_reason"),
    )


class LeaveEndpoint:
    def __init__(self, hrms_client: HRMSClient) -> None:
        self._client = hrms_client

    async def list_types(self) -> list[LeaveType]:
        data = await self._client.get("/api/v1/leave/telegram/types/")
        return [_parse_leave_type(item) for item in data]

    async def get_balances(self, *, telegram_user_id: int, year: int | None = None) -> list[LeaveBalance]:
        params: dict[str, object] = {"telegram_user_id": telegram_user_id}
        if year is not None:
            params["year"] = year
        data = await self._client.get("/api/v1/leave/telegram/balance/", params=params)
        return [_parse_leave_balance(item) for item in data]

    async def get_history(
        self, *, telegram_user_id: int, status: str | None = None, page: int = 1, page_size: int = 5
    ) -> LeaveHistoryPage:
        params: dict[str, object] = {"telegram_user_id": telegram_user_id, "page": page, "page_size": page_size}
        if status is not None:
            params["status"] = status
        data, meta = await self._client.get_with_meta("/api/v1/leave/telegram/requests/", params=params)
        return LeaveHistoryPage(
            items=[_parse_leave_request(item) for item in data],
            page=meta.get("page", page),
            page_size=meta.get("page_size", page_size),
            total_count=meta.get("total_count", len(data)),
            total_pages=meta.get("total_pages", 1),
        )

    async def get_detail(self, *, telegram_user_id: int, leave_request_id: str) -> LeaveRequest:
        data = await self._client.get(
            f"/api/v1/leave/telegram/requests/{leave_request_id}/", params={"telegram_user_id": telegram_user_id}
        )
        return _parse_leave_request(data)

    async def apply(
        self,
        *,
        telegram_user_id: int,
        leave_type_id: str,
        start_date: str,
        end_date: str,
        reason: str | None,
    ) -> LeaveRequest:
        data = await self._client.post(
            "/api/v1/leave/telegram/requests/apply/",
            json_body={
                "telegram_user_id": telegram_user_id,
                "leave_type_id": leave_type_id,
                "start_date": start_date,
                "end_date": end_date,
                "reason": reason,
            },
        )
        return _parse_leave_request(data)

    async def cancel(
        self, *, telegram_user_id: int, leave_request_id: str, cancellation_reason: str | None
    ) -> LeaveRequest:
        data = await self._client.post(
            f"/api/v1/leave/telegram/requests/{leave_request_id}/cancel/",
            json_body={"telegram_user_id": telegram_user_id, "cancellation_reason": cancellation_reason},
        )
        return _parse_leave_request(data)
