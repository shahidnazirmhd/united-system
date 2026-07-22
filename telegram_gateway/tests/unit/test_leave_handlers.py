"""Unit tests for handlers/leave_handlers.py — every Leave command and
callback, exercised through the handler functions directly (matching
test_link_handler.py's/test_profile_handler.py's precedent), plus one
end-to-end walk of the Apply Leave conversation through update_router.route()
to prove the free-text routing itself works, not just the handler in
isolation.
"""
from __future__ import annotations

from src.api_client.endpoints.leave import LeaveBalance, LeaveHistoryPage, LeaveRequest, LeaveType
from src.auth.account_linking import AccountLinkingService
from src.auth.leave_application import LeaveApplicationService
from src.handlers import leave_handlers
from src.handlers.context import HandlerContext
from src.webhook.update_router import Dependencies, route
from tests.fakes import (
    FakeBotAPIClient,
    FakeCallbackQuery,
    FakeEmployeesEndpoint,
    FakeLeaveEndpoint,
    FakeRedis,
    FakeTelegramUpdate,
    make_hrms_error,
)

_ANNUAL = LeaveType(
    id="lt-annual", name="Annual Leave", code="ANNUAL", default_annual_days="20.00",
    is_paid=True, requires_approval=True, is_active=True,
)
_SICK = LeaveType(
    id="lt-sick", name="Sick Leave", code="SICK", default_annual_days="10.00",
    is_paid=True, requires_approval=True, is_active=True,
)

_BALANCE = LeaveBalance(
    employee_id="emp-1", leave_type_id="lt-annual", leave_type_name="Annual Leave", year=2026,
    entitled_days="20.00", used_days="3.00", carried_forward_days="0.00", available_days="17.00", pending_days="2.00",
)

_PENDING_REQUEST = LeaveRequest(
    id="req-1", employee_id="emp-1", leave_type_id="lt-annual", leave_type_name="Annual Leave",
    start_date="2026-09-01", end_date="2026-09-03", total_days="3.00", reason="Trip", status="pending",
    approved_by=None, decided_at=None, decision_comments=None, cancelled_at=None, cancellation_reason=None,
)

_REJECTED_REQUEST = LeaveRequest(
    id="req-2", employee_id="emp-1", leave_type_id="lt-sick", leave_type_name="Sick Leave",
    start_date="2026-05-01", end_date="2026-05-02", total_days="2.00", reason=None, status="rejected",
    approved_by=None, decided_at="2026-04-20T10:00:00Z", decision_comments="Not enough coverage",
    cancelled_at=None, cancellation_reason=None,
)


def _ctx(update, *, leave=None, redis=None) -> HandlerContext:
    leave = leave or FakeLeaveEndpoint()
    employees = FakeEmployeesEndpoint()
    r = redis or FakeRedis()
    return HandlerContext(
        update=update,
        bot=FakeBotAPIClient(),
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, r),
    )


# --- Leave Types ----------------------------------------------------------


async def test_leave_types_lists_names_and_codes():
    leave = FakeLeaveEndpoint(types=[_ANNUAL, _SICK])
    ctx = _ctx(FakeTelegramUpdate(text="/leave_types"), leave=leave)

    await leave_handlers.handle_leave_types(ctx)

    text = ctx.bot.sent_messages[0]["text"]
    assert "Annual Leave" in text
    assert "ANNUAL" in text
    assert "Sick Leave" in text


async def test_leave_types_shows_friendly_message_on_backend_error():
    leave = FakeLeaveEndpoint(raise_on_list_types=make_hrms_error("backend_unreachable", status_code=503))
    ctx = _ctx(FakeTelegramUpdate(text="/leave_types"), leave=leave)

    await leave_handlers.handle_leave_types(ctx)

    assert "trouble reaching" in ctx.bot.sent_messages[0]["text"]


# --- Leave Balance ------------------------------------------------------


async def test_leave_balance_shows_formatted_balances():
    leave = FakeLeaveEndpoint(balances=[_BALANCE])
    ctx = _ctx(FakeTelegramUpdate(text="/leave_balance"), leave=leave)

    await leave_handlers.handle_leave_balance(ctx)

    text = ctx.bot.sent_messages[0]["text"]
    assert "Annual Leave" in text
    assert "17.00" in text


# --- Apply Leave (multi-step) -------------------------------------------


async def test_apply_leave_start_shows_type_selection_keyboard():
    leave = FakeLeaveEndpoint(types=[_ANNUAL, _SICK])
    ctx = _ctx(FakeTelegramUpdate(text="/apply_leave"), leave=leave)

    await leave_handlers.handle_apply_leave_start(ctx)

    sent = ctx.bot.sent_messages[0]
    assert sent["reply_markup"] is not None
    assert len(sent["reply_markup"]["inline_keyboard"]) == 3  # 2 types + cancel row


async def test_apply_leave_start_with_no_types_configured():
    leave = FakeLeaveEndpoint(types=[])
    ctx = _ctx(FakeTelegramUpdate(text="/apply_leave"), leave=leave)

    await leave_handlers.handle_apply_leave_start(ctx)

    assert "No leave types" in ctx.bot.sent_messages[0]["text"]


async def test_apply_leave_type_selected_starts_conversation():
    leave = FakeLeaveEndpoint(types=[_ANNUAL, _SICK])
    ctx = _ctx(
        FakeTelegramUpdate(callback_data="leave:apply:type:lt-annual", callback_query=FakeCallbackQuery()),
        leave=leave,
    )

    await leave_handlers.handle_apply_leave_type_selected(ctx)

    state = await ctx.leave_application.get_state(ctx.telegram_user_id)
    assert state.leave_type_id == "lt-annual"
    assert state.leave_type_name == "Annual Leave"
    assert "start date" in ctx.bot.sent_messages[-1]["text"]


async def test_apply_leave_type_selected_rejects_unknown_type():
    leave = FakeLeaveEndpoint(types=[_ANNUAL])
    ctx = _ctx(
        FakeTelegramUpdate(callback_data="leave:apply:type:does-not-exist", callback_query=FakeCallbackQuery()),
        leave=leave,
    )

    await leave_handlers.handle_apply_leave_type_selected(ctx)

    assert "no longer available" in ctx.bot.sent_messages[-1]["text"]
    assert await ctx.leave_application.is_active(ctx.telegram_user_id) is False


async def test_apply_leave_abort_clears_state():
    leave = FakeLeaveEndpoint()
    ctx = _ctx(FakeTelegramUpdate(callback_data="leave:apply:abort", callback_query=FakeCallbackQuery()), leave=leave)
    await ctx.leave_application.start(telegram_user_id=ctx.telegram_user_id, leave_type_id="lt-annual", leave_type_name="Annual Leave")

    await leave_handlers.handle_apply_leave_abort(ctx)

    assert await ctx.leave_application.is_active(ctx.telegram_user_id) is False
    assert "No leave application was submitted" in ctx.bot.sent_messages[-1]["text"]


async def test_apply_leave_free_text_walks_through_all_steps_to_confirmation():
    leave = FakeLeaveEndpoint()
    ctx = _ctx(FakeTelegramUpdate(text="2026-09-01"), leave=leave)
    await ctx.leave_application.start(telegram_user_id=ctx.telegram_user_id, leave_type_id="lt-annual", leave_type_name="Annual Leave")

    await leave_handlers.handle_apply_leave_free_text(ctx)
    assert "end date" in ctx.bot.sent_messages[-1]["text"]

    ctx.update.text = "2026-09-03"
    await leave_handlers.handle_apply_leave_free_text(ctx)
    assert "reason" in ctx.bot.sent_messages[-1]["text"].lower()

    ctx.update.text = "Family trip"
    await leave_handlers.handle_apply_leave_free_text(ctx)
    last = ctx.bot.sent_messages[-1]
    assert "confirm" in last["text"].lower()
    assert "Family trip" in last["text"]
    assert last["reply_markup"] is not None


async def test_apply_leave_free_text_shows_friendly_message_for_bad_date():
    leave = FakeLeaveEndpoint()
    ctx = _ctx(FakeTelegramUpdate(text="not-a-date"), leave=leave)
    await ctx.leave_application.start(telegram_user_id=ctx.telegram_user_id, leave_type_id="lt-annual", leave_type_name="Annual Leave")

    await leave_handlers.handle_apply_leave_free_text(ctx)

    assert "doesn't look like a date" in ctx.bot.sent_messages[-1]["text"]
    state = await ctx.leave_application.get_state(ctx.telegram_user_id)
    assert state.step == "start_date"  # unchanged — bad input must not advance the flow


async def test_apply_leave_confirm_submits_and_shows_result():
    leave = FakeLeaveEndpoint(apply_result=_PENDING_REQUEST)
    ctx = _ctx(FakeTelegramUpdate(callback_data="leave:apply:confirm", callback_query=FakeCallbackQuery()), leave=leave)
    await ctx.leave_application.start(telegram_user_id=ctx.telegram_user_id, leave_type_id="lt-annual", leave_type_name="Annual Leave")
    await ctx.leave_application.submit_start_date(ctx.telegram_user_id, "2026-09-01")
    await ctx.leave_application.submit_end_date(ctx.telegram_user_id, "2026-09-03")
    await ctx.leave_application.submit_reason(ctx.telegram_user_id, "skip")

    await leave_handlers.handle_apply_leave_confirm(ctx)

    text = ctx.bot.sent_messages[-1]["text"]
    assert "submitted" in text
    assert "req-1" in text


async def test_apply_leave_confirm_shows_friendly_message_on_backend_rejection():
    leave = FakeLeaveEndpoint(raise_on_apply=make_hrms_error("overlapping_leave_request", status_code=422))
    ctx = _ctx(FakeTelegramUpdate(callback_data="leave:apply:confirm", callback_query=FakeCallbackQuery()), leave=leave)
    await ctx.leave_application.start(telegram_user_id=ctx.telegram_user_id, leave_type_id="lt-annual", leave_type_name="Annual Leave")
    await ctx.leave_application.submit_start_date(ctx.telegram_user_id, "2026-09-01")
    await ctx.leave_application.submit_end_date(ctx.telegram_user_id, "2026-09-03")
    await ctx.leave_application.submit_reason(ctx.telegram_user_id, "skip")

    await leave_handlers.handle_apply_leave_confirm(ctx)

    assert "overlap" in ctx.bot.sent_messages[-1]["text"]


async def test_full_apply_leave_conversation_via_update_router():
    """End-to-end: /apply_leave -> tap a type -> three free-text replies ->
    tap confirm, routed entirely through update_router.route() the way
    real Telegram webhooks would drive it — proves the free-text dispatch
    wiring in update_router.py, not just the handler functions in
    isolation."""
    leave = FakeLeaveEndpoint(types=[_ANNUAL], apply_result=_PENDING_REQUEST)
    employees = FakeEmployeesEndpoint()
    redis = FakeRedis()
    bot = FakeBotAPIClient()
    deps = Dependencies(
        bot=bot,
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, redis),
    )

    await route(FakeTelegramUpdate(text="/apply_leave"), deps, leave_handlers.registry)
    assert bot.sent_messages[-1]["reply_markup"] is not None

    await route(
        FakeTelegramUpdate(callback_data="leave:apply:type:lt-annual", callback_query=FakeCallbackQuery()), deps, leave_handlers.registry
    )
    assert "start date" in bot.sent_messages[-1]["text"]

    await route(FakeTelegramUpdate(text="2026-09-01"), deps, leave_handlers.registry)
    assert "end date" in bot.sent_messages[-1]["text"]

    await route(FakeTelegramUpdate(text="2026-09-03"), deps, leave_handlers.registry)
    assert "reason" in bot.sent_messages[-1]["text"].lower()

    await route(FakeTelegramUpdate(text="skip"), deps, leave_handlers.registry)
    assert "confirm" in bot.sent_messages[-1]["text"].lower()

    await route(
        FakeTelegramUpdate(callback_data="leave:apply:confirm", callback_query=FakeCallbackQuery()), deps, leave_handlers.registry
    )
    assert "submitted" in bot.sent_messages[-1]["text"]
    assert leave.apply_calls[0]["start_date"] == "2026-09-01"
    assert leave.apply_calls[0]["end_date"] == "2026-09-03"


# --- Leave History / Detail ----------------------------------------------


async def test_leave_history_shows_formatted_list():
    page = LeaveHistoryPage(items=[_PENDING_REQUEST], page=1, page_size=5, total_count=1, total_pages=1)
    leave = FakeLeaveEndpoint(history=page)
    ctx = _ctx(FakeTelegramUpdate(text="/leave_history"), leave=leave)

    await leave_handlers.handle_leave_history(ctx)

    text = ctx.bot.sent_messages[0]["text"]
    assert "req-1" in text
    assert "Page 1 of 1" in text


async def test_leave_history_parses_page_argument():
    leave = FakeLeaveEndpoint(history=LeaveHistoryPage(items=[], page=2, page_size=5, total_count=0, total_pages=2))
    ctx = _ctx(FakeTelegramUpdate(text="/leave_history 2"), leave=leave)

    await leave_handlers.handle_leave_history(ctx)

    assert leave.history_calls[0]["page"] == 2


async def test_leave_history_empty_shows_friendly_message():
    leave = FakeLeaveEndpoint(history=LeaveHistoryPage(items=[], page=1, page_size=5, total_count=0, total_pages=1))
    ctx = _ctx(FakeTelegramUpdate(text="/leave_history"), leave=leave)

    await leave_handlers.handle_leave_history(ctx)

    assert "don't have any leave requests" in ctx.bot.sent_messages[0]["text"]


async def test_leave_request_detail_requires_an_id():
    ctx = _ctx(FakeTelegramUpdate(text="/leave_request"))

    await leave_handlers.handle_leave_request_detail(ctx)

    assert "leave request ID" in ctx.bot.sent_messages[0]["text"]


async def test_leave_request_detail_shows_formatted_card():
    leave = FakeLeaveEndpoint(detail=_REJECTED_REQUEST)
    ctx = _ctx(FakeTelegramUpdate(text="/leave_request req-2"), leave=leave)

    await leave_handlers.handle_leave_request_detail(ctx)

    text = ctx.bot.sent_messages[0]["text"]
    assert "Sick Leave" in text
    assert "Not enough coverage" in text
    assert leave.detail_calls[0]["leave_request_id"] == "req-2"


# --- Cancel Leave Request -------------------------------------------------


async def test_cancel_leave_start_shows_only_cancellable_requests():
    approved = LeaveRequest(
        id="req-3", employee_id="emp-1", leave_type_id="lt-annual", leave_type_name="Annual Leave",
        start_date="2026-10-01", end_date="2026-10-02", total_days="2.00", reason=None, status="approved",
        approved_by="hr-1", decided_at="2026-09-20T00:00:00Z", decision_comments=None, cancelled_at=None,
        cancellation_reason=None,
    )
    page = LeaveHistoryPage(items=[_PENDING_REQUEST, _REJECTED_REQUEST, approved], page=1, page_size=50, total_count=3, total_pages=1)
    leave = FakeLeaveEndpoint(history=page)
    ctx = _ctx(FakeTelegramUpdate(text="/cancel_leave"), leave=leave)

    await leave_handlers.handle_cancel_leave_start(ctx)

    sent = ctx.bot.sent_messages[0]
    button_data = [btn["callback_data"] for row in sent["reply_markup"]["inline_keyboard"] for btn in row]
    assert "leave:cancel:select:req-1" in button_data
    assert "leave:cancel:select:req-3" in button_data
    assert "leave:cancel:select:req-2" not in button_data  # rejected — not cancellable


async def test_cancel_leave_start_with_nothing_cancellable():
    page = LeaveHistoryPage(items=[_REJECTED_REQUEST], page=1, page_size=50, total_count=1, total_pages=1)
    leave = FakeLeaveEndpoint(history=page)
    ctx = _ctx(FakeTelegramUpdate(text="/cancel_leave"), leave=leave)

    await leave_handlers.handle_cancel_leave_start(ctx)

    assert "don't have any pending or approved" in ctx.bot.sent_messages[0]["text"]


async def test_cancel_leave_selected_shows_confirmation():
    leave = FakeLeaveEndpoint(detail=_PENDING_REQUEST)
    ctx = _ctx(
        FakeTelegramUpdate(callback_data="leave:cancel:select:req-1", callback_query=FakeCallbackQuery()), leave=leave
    )

    await leave_handlers.handle_cancel_leave_selected(ctx)

    sent = ctx.bot.sent_messages[-1]
    assert "Cancel this request" in sent["text"]
    assert sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "leave:cancel:confirm:req-1"


async def test_cancel_leave_confirmed_cancels_and_shows_result():
    cancelled_result = LeaveRequest(
        id="req-1", employee_id="emp-1", leave_type_id="lt-annual", leave_type_name="Annual Leave",
        start_date="2026-09-01", end_date="2026-09-03", total_days="3.00", reason="Trip", status="cancelled",
        approved_by=None, decided_at=None, decision_comments=None, cancelled_at="2026-08-01T00:00:00Z",
        cancellation_reason=None,
    )
    leave = FakeLeaveEndpoint(cancel_result=cancelled_result)
    ctx = _ctx(
        FakeTelegramUpdate(callback_data="leave:cancel:confirm:req-1", callback_query=FakeCallbackQuery()), leave=leave
    )

    await leave_handlers.handle_cancel_leave_confirmed(ctx)

    assert leave.cancel_calls[0]["leave_request_id"] == "req-1"
    assert "cancelled" in ctx.bot.sent_messages[-1]["text"]


async def test_cancel_leave_confirmed_shows_friendly_message_on_error():
    leave = FakeLeaveEndpoint(raise_on_cancel=make_hrms_error("leave_request_not_cancellable", status_code=409))
    ctx = _ctx(
        FakeTelegramUpdate(callback_data="leave:cancel:confirm:req-1", callback_query=FakeCallbackQuery()), leave=leave
    )

    await leave_handlers.handle_cancel_leave_confirmed(ctx)

    assert "no longer be cancelled" in ctx.bot.sent_messages[-1]["text"]


async def test_cancel_leave_aborted_makes_no_changes():
    ctx = _ctx(FakeTelegramUpdate(callback_data="leave:cancel:abort", callback_query=FakeCallbackQuery()))

    await leave_handlers.handle_cancel_leave_aborted(ctx)

    assert "No changes made" in ctx.bot.sent_messages[-1]["text"]
