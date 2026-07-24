"""Outbound calls to the Telegram Bot API.

Per HRMS_Folder_Structure.md section 3.2: "it has no knowledge of HR data,
it just knows how to talk to Telegram." This file never imports anything
from `api_client/` or `handlers/` — the dependency direction is strictly
handlers -> bot_api_client, never the reverse.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from src.errors import TelegramAPIError
from src.logging_config import log_event

logger = logging.getLogger(__name__)

_BOT_API_BASE = "https://api.telegram.org/bot{token}"


class BotAPIClient:
    def __init__(self, bot_token: str, *, timeout_seconds: float = 10.0) -> None:
        self._base_url = _BOT_API_BASE.format(token=bot_token)
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._call("sendMessage", payload)

    async def edit_message_text(
        self,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._call("editMessageText", payload)

    async def edit_message_reply_markup(
        self,
        *,
        chat_id: int,
        message_id: int,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """`editMessageReplyMarkup` — changes (or, with an empty keyboard,
        removes) a message's inline keyboard without touching its text.
        The counterpart to `edit_message_text` for callers that only need
        to strip stale buttons off a message once they've been acted on
        (see `handlers/context.py`'s `clear_reply_markup`), not change
        what it says."""
        payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._call("editMessageReplyMarkup", payload)

    async def answer_callback_query(
        self, *, callback_query_id: str, text: str | None = None, show_alert: bool = False
    ) -> dict[str, Any]:
        """Must be called for every callback query within Telegram's ~30s
        window, even with no `text` — otherwise the tapping user sees a
        perpetual loading spinner on the inline button."""
        payload: dict[str, Any] = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text is not None:
            payload["text"] = text
        return await self._call("answerCallbackQuery", payload)

    async def set_webhook(self, *, url: str, secret_token: str) -> dict[str, Any]:
        return await self._call("setWebhook", {"url": url, "secret_token": secret_token})

    async def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._client.post(f"/{method}", json=payload)
        except httpx.HTTPError as exc:
            log_event(logger, logging.ERROR, "telegram_api_transport_error", method=method, error=str(exc))
            raise TelegramAPIError(f"Transport error calling Telegram {method}: {exc}") from exc

        body = response.json()
        if not body.get("ok", False):
            description = body.get("description")
            log_event(
                logger,
                logging.ERROR,
                "telegram_api_error_response",
                method=method,
                status_code=response.status_code,
                description=description,
            )
            raise TelegramAPIError(f"Telegram {method} failed: {description}", description=description)
        return body.get("result", {})
