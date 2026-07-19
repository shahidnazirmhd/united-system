"""Base authenticated HTTP client for the HRMS backend.

Per HRMS_Folder_Structure.md section 3.3, this whole package is "the folder
that makes 'no database access from Telegram Gateway' true as a structural
fact": it contains HTTP client code and nothing else. No ORM import is
possible because none is a dependency of this service (see
telegram_gateway/requirements.txt — no psycopg, no Django).

Employee & Telegram Authentication refactor: this service no longer holds
any per-employee credential (no JWT, no refresh token — see
auth/account_linking.py's module docstring for the full reasoning). Every
call this service makes to the backend is authenticated the same way,
regardless of which employee it's about: a single static shared secret
(`X-Internal-Service-Key`, matching `shared_kernel.api.permissions.
HasInternalServiceKey` on the Django side), attached once at construction
time rather than threaded through every individual request. *Which*
employee a call is about is carried as an ordinary request parameter
(`telegram_user_id`), not as a credential — the backend's
`HasInternalServiceKey` permission answers "is this caller the Gateway,"
never "which employee is this."

This class does exactly one thing: send the request and translate the
backend's `{"success": false, "error": {...}}` envelope into
`HRMSAPIError`. It does NOT decide what a response means for a particular
employee — that's `api_client/endpoints/employees.py`'s job.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from src.errors import HRMSAPIError
from src.logging_config import log_event

logger = logging.getLogger(__name__)


class HRMSClient:
    def __init__(self, base_url: str, *, internal_service_key: str, timeout_seconds: float = 10.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            headers={"X-Internal-Service-Key": internal_service_key},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(method, path, json=json_body, params=params)
        except httpx.HTTPError as exc:
            log_event(logger, logging.ERROR, "hrms_api_transport_error", method=method, path=path, error=str(exc))
            raise HRMSAPIError(status_code=503, code="backend_unreachable", message=str(exc)) from exc

        body: dict[str, Any] = {}
        try:
            body = response.json()
        except ValueError:
            pass

        log_event(
            logger,
            logging.INFO,
            "hrms_api_call",
            method=method,
            path=path,
            status_code=response.status_code,
            success=body.get("success"),
        )

        if not response.is_success or not body.get("success", False):
            error = body.get("error", {})
            raise HRMSAPIError(
                status_code=response.status_code,
                code=error.get("code", "unknown_error"),
                message=error.get("message", "The HRMS API returned an unexpected error."),
            )

        return body.get("data", {})

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, *, json_body: dict[str, Any] | None = None) -> dict:
        return await self.request("POST", path, json_body=json_body)
