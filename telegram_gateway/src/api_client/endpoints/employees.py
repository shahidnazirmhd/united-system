"""One file per backend module the Gateway calls — this one talks only to
`apps/employees`'s Telegram-facing endpoints, mirroring the backend's own
module boundary (HRMS_Folder_Structure.md section 3.3). A future
`endpoints/leave.py` would call only Leave's endpoints, never reach into
this file or vice versa.

Employee & Telegram Authentication refactor: Telegram linking used to be
split across two backend modules (Identity issued tokens, Employee served
profiles) — it's now entirely `apps/employees`, so this one file is now
also the only place that knows about linking, replacing the deleted
`api_client/auth_client.py`. Every method here maps 1:1 to one of the
Gateway-facing endpoints at `apps/employees/interface/telegram_views.py`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Type hint only — see api_client/hrms_client.py's identical note.
    from src.api_client.hrms_client import HRMSClient


@dataclass(frozen=True)
class EmployeeProfile:
    id: str
    employee_code: str
    full_name: str
    job_title: str
    work_email: str
    phone_number: str | None
    department_name: str | None
    manager_name: str | None
    employment_type: str
    date_of_joining: str
    status: str
    is_linked_to_telegram: bool
    telegram_username: str | None


@dataclass(frozen=True)
class TelegramLinkStatus:
    is_linked: bool
    telegram_username: str | None
    linked_at: str | None


def _parse_employee_profile(data: dict) -> EmployeeProfile:
    return EmployeeProfile(
        id=data["id"],
        employee_code=data["employee_code"],
        full_name=data["full_name"],
        job_title=data["job_title"],
        work_email=data["work_email"],
        phone_number=data.get("phone_number"),
        department_name=data.get("department_name"),
        manager_name=data.get("manager_name"),
        employment_type=data["employment_type"],
        date_of_joining=data["date_of_joining"],
        status=data["status"],
        is_linked_to_telegram=data.get("is_linked_to_telegram", False),
        telegram_username=data.get("telegram_username"),
    )


class EmployeesEndpoint:
    def __init__(self, hrms_client: HRMSClient) -> None:
        self._client = hrms_client

    async def get_profile(self, *, telegram_user_id: int) -> EmployeeProfile:
        """Backs both "My Profile" and "Employment Status" — see
        formatting/profile_formatter.py for why one backend call serves
        two different Telegram views. Raises HRMSAPIError
        (code="employee_not_linked_to_telegram") if this Telegram user id
        has no employee linked."""
        data = await self._client.get(
            "/api/v1/employees/telegram/profile/", params={"telegram_user_id": telegram_user_id}
        )
        return _parse_employee_profile(data)

    async def request_link(
        self, *, employee_code: str, telegram_user_id: int, chat_id: int, telegram_username: str | None
    ) -> None:
        await self._client.post(
            "/api/v1/employees/telegram/link/request/",
            json_body={
                "employee_code": employee_code,
                "telegram_user_id": telegram_user_id,
                "chat_id": chat_id,
                "telegram_username": telegram_username,
            },
        )

    async def verify_link(
        self, *, telegram_user_id: int, chat_id: int, otp: str, telegram_username: str | None
    ) -> EmployeeProfile:
        data = await self._client.post(
            "/api/v1/employees/telegram/link/verify/",
            json_body={
                "telegram_user_id": telegram_user_id,
                "chat_id": chat_id,
                "otp": otp,
                "telegram_username": telegram_username,
            },
        )
        return _parse_employee_profile(data)

    async def unlink(self, *, telegram_user_id: int) -> None:
        await self._client.post(
            "/api/v1/employees/telegram/unlink/", json_body={"telegram_user_id": telegram_user_id}
        )

    async def get_link_status(self, *, telegram_user_id: int) -> TelegramLinkStatus:
        data = await self._client.get(
            "/api/v1/employees/telegram/status/", params={"telegram_user_id": telegram_user_id}
        )
        return TelegramLinkStatus(
            is_linked=data["is_linked"],
            telegram_username=data.get("telegram_username"),
            linked_at=data.get("linked_at"),
        )
