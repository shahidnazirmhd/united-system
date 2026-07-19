"""Shapes of Telegram's own update/message payloads.

Deliberately separate from `api_client/` (the HRMS's wire format) per
HRMS_Folder_Structure.md section 3.2 — "Telegram's wire format and the
HRMS's wire format are never confused with each other." These are Pydantic
models parsing exactly (and only) the subset of the Bot API's Update object
this service actually uses; unused fields are ignored rather than modeled,
since a full mirror of Telegram's schema is not this file's job.

`from_`/alias="from": Telegram's JSON field is literally named `from`, a
Python reserved word — `populate_by_name=True` plus a Field alias is
Pydantic v2's supported way to parse it into a legally-named attribute.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    type: str


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    is_bot: bool = False
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    message_id: int
    chat: TelegramChat
    from_user: TelegramUser | None = Field(default=None, alias="from")
    text: str | None = None


class TelegramCallbackQuery(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    from_user: TelegramUser = Field(alias="from")
    message: TelegramMessage | None = None
    data: str | None = None


class TelegramUpdate(BaseModel):
    """The top-level object Telegram POSTs to the webhook. Only `message`
    and `callback_query` are modeled — this Gateway does not (yet) handle
    edited messages, inline queries, or other update kinds; `update_router`
    treats an update matching none of these as a no-op, not an error."""

    model_config = ConfigDict(extra="ignore")

    update_id: int
    message: TelegramMessage | None = None
    callback_query: TelegramCallbackQuery | None = None

    @property
    def chat_id(self) -> int | None:
        if self.message is not None:
            return self.message.chat.id
        if self.callback_query is not None and self.callback_query.message is not None:
            return self.callback_query.message.chat.id
        return None

    @property
    def telegram_user_id(self) -> int | None:
        if self.message is not None and self.message.from_user is not None:
            return self.message.from_user.id
        if self.callback_query is not None:
            return self.callback_query.from_user.id
        return None

    @property
    def telegram_username(self) -> str | None:
        user = self.message.from_user if self.message is not None else (
            self.callback_query.from_user if self.callback_query is not None else None
        )
        return user.username if user is not None else None

    @property
    def text(self) -> str | None:
        return self.message.text if self.message is not None else None

    @property
    def callback_data(self) -> str | None:
        return self.callback_query.data if self.callback_query is not None else None
