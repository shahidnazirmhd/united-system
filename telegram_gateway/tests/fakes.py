"""Hand-rolled async fakes for every I/O boundary this service depends on —
no pytest plugins, no mocking library, matching the backend's own
"fake repositories, not mocks" testing discipline
(apps/identity/tests/unit/test_login_user_use_case.py) exactly, adapted to
this service's async collaborators.

None of these fakes import httpx/redis/fastapi — they satisfy the
duck-typed shape AccountLinkingService/handlers actually call, which is all
Python's dynamic typing requires and all the TYPE_CHECKING-guarded imports
throughout src/ were written to allow.

Employee & Telegram Authentication refactor: FakeAuthClient/FakeTokenStore
(Phase 7) are gone along with the classes they faked (api_client/
auth_client.py, auth/token_store.py, auth/session.py — all deleted). This
service now authenticates every backend call with one static internal
service key, never a per-employee token, so there is nothing left to fake
at that layer — FakeEmployeesEndpoint below is the single fake standing in
for every backend call this service makes (profile reads AND Telegram
linking), matching the production `EmployeesEndpoint`'s own merged shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.api_client.endpoints.employees import EmployeeProfile, TelegramLinkStatus
from src.api_client.endpoints.leave import LeaveHistoryPage
from src.errors import HRMSAPIError


class FakeRedis:
    """In-memory equivalent of redis.asyncio.Redis, implementing only the
    handful of commands this service actually calls (get/set/delete/exists/
    incr/expire) — a fake of the *shape this codebase uses*, not a full
    Redis reimplementation."""

    def __init__(self) -> None:
        self._data: dict[str, bytes | str] = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def set(self, key: str, value, ex: int | None = None) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    async def incr(self, key: str) -> int:
        current = int(self._data.get(key, 0)) + 1
        self._data[key] = current
        return current

    async def expire(self, key: str, seconds: int) -> None:
        pass  # TTL semantics aren't exercised by these tests — see test_rate_limiter.py's scope note.


@dataclass
class FakeEmployeesEndpoint:
    """Configurable success/failure per method — tests set `raise_on_*`
    before calling, rather than this class trying to model the backend's
    actual OTP/link semantics (that's the backend's own test suite's job).

    `profile` doubles as both "what get_profile returns" and "what
    verify_link returns on success" (verify_result overrides the latter if
    set explicitly) — mirrors how the real backend returns the same
    EmployeeResponse shape from both endpoints.
    """

    profile: EmployeeProfile | None = None
    verify_result: EmployeeProfile | None = None
    link_status: TelegramLinkStatus | None = None

    raise_on_get_profile: Exception | None = None
    raise_on_request_link: Exception | None = None
    raise_on_verify_link: Exception | None = None
    raise_on_unlink: Exception | None = None

    profile_calls: list[int] = field(default_factory=list)
    link_requests: list[dict] = field(default_factory=list)
    verify_calls: list[dict] = field(default_factory=list)
    unlink_calls: list[int] = field(default_factory=list)
    status_calls: list[int] = field(default_factory=list)

    async def get_profile(self, *, telegram_user_id: int) -> EmployeeProfile:
        self.profile_calls.append(telegram_user_id)
        if self.raise_on_get_profile is not None:
            raise self.raise_on_get_profile
        return self.profile

    async def request_link(self, *, employee_code, telegram_user_id, chat_id, telegram_username):
        self.link_requests.append(
            {
                "employee_code": employee_code,
                "telegram_user_id": telegram_user_id,
                "chat_id": chat_id,
                "telegram_username": telegram_username,
            }
        )
        if self.raise_on_request_link is not None:
            raise self.raise_on_request_link

    async def verify_link(self, *, telegram_user_id, chat_id, otp, telegram_username) -> EmployeeProfile:
        self.verify_calls.append({"telegram_user_id": telegram_user_id, "chat_id": chat_id, "otp": otp})
        if self.raise_on_verify_link is not None:
            raise self.raise_on_verify_link
        return self.verify_result or self.profile

    async def unlink(self, *, telegram_user_id: int) -> None:
        self.unlink_calls.append(telegram_user_id)
        if self.raise_on_unlink is not None:
            raise self.raise_on_unlink

    async def get_link_status(self, *, telegram_user_id: int) -> TelegramLinkStatus:
        self.status_calls.append(telegram_user_id)
        return self.link_status or TelegramLinkStatus(is_linked=False, telegram_username=None, linked_at=None)


@dataclass
class FakeLeaveEndpoint:
    """Configurable success/failure per method, same convention as
    `FakeEmployeesEndpoint` — tests set `raise_on_*`/return values before
    calling, rather than this class modeling the backend's actual
    validation rules (that's the backend's own test suite's job)."""

    types: list = field(default_factory=list)
    balances: list = field(default_factory=list)
    history: LeaveHistoryPage | None = None
    detail: object | None = None
    apply_result: object | None = None
    cancel_result: object | None = None

    raise_on_list_types: Exception | None = None
    raise_on_get_balances: Exception | None = None
    raise_on_get_history: Exception | None = None
    raise_on_get_detail: Exception | None = None
    raise_on_apply: Exception | None = None
    raise_on_cancel: Exception | None = None

    apply_calls: list[dict] = field(default_factory=list)
    cancel_calls: list[dict] = field(default_factory=list)
    detail_calls: list[dict] = field(default_factory=list)
    history_calls: list[dict] = field(default_factory=list)

    async def list_types(self):
        if self.raise_on_list_types is not None:
            raise self.raise_on_list_types
        return self.types

    async def get_balances(self, *, telegram_user_id, year=None):
        if self.raise_on_get_balances is not None:
            raise self.raise_on_get_balances
        return self.balances

    async def get_history(self, *, telegram_user_id, status=None, page=1, page_size=5):
        self.history_calls.append({"telegram_user_id": telegram_user_id, "status": status, "page": page})
        if self.raise_on_get_history is not None:
            raise self.raise_on_get_history
        return self.history or LeaveHistoryPage(items=[], page=page, page_size=page_size, total_count=0, total_pages=1)

    async def get_detail(self, *, telegram_user_id, leave_request_id):
        self.detail_calls.append({"telegram_user_id": telegram_user_id, "leave_request_id": leave_request_id})
        if self.raise_on_get_detail is not None:
            raise self.raise_on_get_detail
        return self.detail

    async def apply(self, *, telegram_user_id, leave_type_id, start_date, end_date, reason):
        self.apply_calls.append(
            {
                "telegram_user_id": telegram_user_id,
                "leave_type_id": leave_type_id,
                "start_date": start_date,
                "end_date": end_date,
                "reason": reason,
            }
        )
        if self.raise_on_apply is not None:
            raise self.raise_on_apply
        return self.apply_result

    async def cancel(self, *, telegram_user_id, leave_request_id, cancellation_reason):
        self.cancel_calls.append(
            {
                "telegram_user_id": telegram_user_id,
                "leave_request_id": leave_request_id,
                "cancellation_reason": cancellation_reason,
            }
        )
        if self.raise_on_cancel is not None:
            raise self.raise_on_cancel
        return self.cancel_result


class FakeBotAPIClient:
    def __init__(self, *, raise_on_edit_message: Exception | None = None) -> None:
        self.sent_messages: list[dict] = []
        self.edited_messages: list[dict] = []
        self.answered_callbacks: list[dict] = []
        self.cleared_markups: list[dict] = []
        self.raise_on_edit_message = raise_on_edit_message

    async def send_message(self, *, chat_id, text, reply_markup=None, parse_mode="Markdown"):
        self.sent_messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return {"message_id": len(self.sent_messages)}

    async def edit_message_text(self, *, chat_id, message_id, text, reply_markup=None, parse_mode="Markdown"):
        if self.raise_on_edit_message is not None:
            raise self.raise_on_edit_message
        self.edited_messages.append(
            {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup}
        )

    async def edit_message_reply_markup(self, *, chat_id, message_id, reply_markup=None):
        self.cleared_markups.append({"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup})

    async def answer_callback_query(self, *, callback_query_id, text=None, show_alert=False):
        self.answered_callbacks.append({"callback_query_id": callback_query_id, "text": text})


def make_hrms_error(code: str, status_code: int = 400, message: str = "error") -> HRMSAPIError:
    return HRMSAPIError(status_code=status_code, code=code, message=message)


# --- Fake Telegram update shapes -----------------------------------------
# Duck-typed stand-ins for telegram_client/types.py's pydantic models —
# deliberately plain dataclasses so handler-level tests don't need pydantic
# installed. HandlerContext only ever accesses `.chat_id`, `.telegram_user_id`,
# `.telegram_username`, `.text`, `.callback_data`, and `.callback_query`
# (with `.id`/`.message.message_id` on the latter) — exactly what's modeled
# here, nothing more.


@dataclass
class FakeCallbackMessage:
    message_id: int = 1


@dataclass
class FakeCallbackQuery:
    id: str = "callback-1"
    message: FakeCallbackMessage | None = field(default_factory=FakeCallbackMessage)


@dataclass
class FakeTelegramUpdate:
    chat_id: int = 42
    telegram_user_id: int = 42
    telegram_username: str | None = "ada"
    text: str | None = None
    callback_data: str | None = None
    callback_query: FakeCallbackQuery | None = None

    @property
    def message(self) -> object | None:
        """webhook/update_router.py's `route()` branches on
        `update.message is not None` vs `update.callback_query is not None`
        to decide which of `_route_message`/`_route_callback` to call — it
        never reads attributes off `.message` itself (message-derived data
        comes through `HandlerContext`'s own `.text`/`.chat_id` properties
        instead). A truthy sentinel here is enough to route correctly
        without needing a full fake Telegram Message object.
        """
        return object() if self.text is not None else None
