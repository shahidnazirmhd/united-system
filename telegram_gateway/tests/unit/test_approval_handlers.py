"""Unit tests for handlers/approval_handlers.py — every Approval Engine
command and callback, exercised through the handler functions directly
(matching test_leave_handlers.py's precedent), plus one end-to-end walk of
the Approve-tap -> comment -> submit flow through update_router.route() to
prove the free-text routing works, not just the handler functions in
isolation.
"""
from __future__ import annotations

from src.api_client.endpoints.approvals import ApprovalRequest, ApprovalStep
from src.auth.account_linking import AccountLinkingService
from src.auth.approval_decision import ApprovalDecisionService
from src.auth.leave_application import LeaveApplicationService
from src.handlers import approval_handlers
from src.handlers.context import HandlerContext
from src.handlers.registry import registry
from src.webhook.update_router import Dependencies, route
from tests.fakes import (
    FakeApprovalsEndpoint,
    FakeBotAPIClient,
    FakeCallbackMessage,
    FakeCallbackQuery,
    FakeEmployeesEndpoint,
    FakeLeaveEndpoint,
    FakeRedis,
    FakeTelegramUpdate,
    make_hrms_error,
)

_PENDING_STEP = ApprovalStep(
    id="step-1", approval_request_id="req-1", level=1, approver_employee_id="mgr-1", status="pending",
    comments=None, decided_at=None,
)
_PENDING_REQUEST = ApprovalRequest(
    id="req-1", subject_type="leave.leave_request", subject_id="leave-req-1", requested_by_employee_id="emp-1",
    subject_summary="Annual Leave: 2026-09-01 -> 2026-09-03 (3 days)", status="pending", current_level=1,
    steps=[_PENDING_STEP],
)
_APPROVED_RESULT = ApprovalRequest(
    id="req-1", subject_type="leave.leave_request", subject_id="leave-req-1", requested_by_employee_id="emp-1",
    subject_summary="Annual Leave: 3 days", status="approved", current_level=1,
)


def _ctx(update, *, approvals=None, redis=None) -> HandlerContext:
    approvals = approvals or FakeApprovalsEndpoint()
    leave = FakeLeaveEndpoint()
    employees = FakeEmployeesEndpoint()
    r = redis or FakeRedis()
    return HandlerContext(
        update=update,
        bot=FakeBotAPIClient(),
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, FakeRedis()),
        approvals=approvals,
        approval_decision=ApprovalDecisionService(approvals, r),
    )


# --- /pending_approvals -----------------------------------------------


async def test_pending_approvals_sends_no_pending_message_when_empty():
    ctx = _ctx(FakeTelegramUpdate(text="/pending_approvals"))

    await approval_handlers.handle_pending_approvals(ctx)

    assert len(ctx.bot.sent_messages) == 1
    assert "no pending approvals" in ctx.bot.sent_messages[0]["text"].lower()


async def test_pending_approvals_sends_one_message_per_item_with_decision_buttons():
    approvals = FakeApprovalsEndpoint(pending=[_PENDING_REQUEST])
    ctx = _ctx(FakeTelegramUpdate(text="/pending_approvals"), approvals=approvals)

    await approval_handlers.handle_pending_approvals(ctx)

    assert len(ctx.bot.sent_messages) == 1
    sent = ctx.bot.sent_messages[0]
    assert "Annual Leave" in sent["text"]
    buttons = sent["reply_markup"]["inline_keyboard"][0]
    assert buttons[0]["callback_data"] == "approval:decide:approve:req-1"
    assert buttons[1]["callback_data"] == "approval:decide:reject:req-1"


async def test_pending_approvals_shows_friendly_message_on_backend_error():
    approvals = FakeApprovalsEndpoint(raise_on_list_pending=make_hrms_error("backend_unreachable", status_code=503))
    ctx = _ctx(FakeTelegramUpdate(text="/pending_approvals"), approvals=approvals)

    await approval_handlers.handle_pending_approvals(ctx)

    assert "trouble reaching" in ctx.bot.sent_messages[0]["text"]


# --- Approve/Reject tap -> comment prompt -------------------------------


async def test_approve_tapped_clears_markup_and_prompts_for_comment():
    update = FakeTelegramUpdate(
        callback_data="approval:decide:approve:req-1", callback_query=FakeCallbackQuery(message=FakeCallbackMessage())
    )
    ctx = _ctx(update)

    await approval_handlers.handle_approve_tapped(ctx)

    assert len(ctx.bot.cleared_markups) == 1
    assert await ctx.approval_decision.is_active(ctx.telegram_user_id) is True
    state = await ctx.approval_decision.get_state(ctx.telegram_user_id)
    assert state.approval_request_id == "req-1"
    assert state.decision == "approve"
    assert "comment" in ctx.bot.sent_messages[0]["text"].lower()


async def test_reject_tapped_starts_decision_with_reject():
    update = FakeTelegramUpdate(
        callback_data="approval:decide:reject:req-1", callback_query=FakeCallbackQuery(message=FakeCallbackMessage())
    )
    ctx = _ctx(update)

    await approval_handlers.handle_reject_tapped(ctx)

    state = await ctx.approval_decision.get_state(ctx.telegram_user_id)
    assert state.decision == "reject"


# --- comment free text --------------------------------------------------


async def test_approval_comment_free_text_submits_and_replies_with_result():
    approvals = FakeApprovalsEndpoint(decide_result=_APPROVED_RESULT)
    ctx = _ctx(FakeTelegramUpdate(text="Have a great trip"), approvals=approvals)
    await ctx.approval_decision.start(telegram_user_id=ctx.telegram_user_id, approval_request_id="req-1", decision="approve")

    await approval_handlers.handle_approval_comment_free_text(ctx)

    assert approvals.decide_calls[0]["comments"] == "Have a great trip"
    assert "Approved" in ctx.bot.sent_messages[0]["text"]


async def test_approval_comment_free_text_shows_friendly_message_on_backend_error():
    approvals = FakeApprovalsEndpoint(
        raise_on_decide=make_hrms_error("approval_request_not_pending", status_code=409)
    )
    ctx = _ctx(FakeTelegramUpdate(text="skip"), approvals=approvals)
    await ctx.approval_decision.start(telegram_user_id=ctx.telegram_user_id, approval_request_id="req-1", decision="approve")

    await approval_handlers.handle_approval_comment_free_text(ctx)

    assert "already been decided" in ctx.bot.sent_messages[0]["text"]


# --- end-to-end through update_router.route() ---------------------------


async def test_full_reject_flow_through_update_router():
    approvals = FakeApprovalsEndpoint(pending=[_PENDING_REQUEST], decide_result=_APPROVED_RESULT)
    employees = FakeEmployeesEndpoint()
    leave = FakeLeaveEndpoint()
    bot = FakeBotAPIClient()
    deps = Dependencies(
        bot=bot,
        linking=AccountLinkingService(employees, FakeRedis()),
        employees=employees,
        leave=leave,
        leave_application=LeaveApplicationService(leave, FakeRedis()),
        approvals=approvals,
        approval_decision=ApprovalDecisionService(approvals, FakeRedis()),
    )

    # Step 1: tap Reject on the notification's inline button.
    tap_update = FakeTelegramUpdate(
        callback_data="approval:decide:reject:req-1", callback_query=FakeCallbackQuery(message=FakeCallbackMessage())
    )
    await route(tap_update, deps, registry)
    assert "comment" in bot.sent_messages[-1]["text"].lower()

    # Step 2: reply with a free-text comment — routed via
    # ctx.approval_decision.is_active(), not a slash command.
    comment_update = FakeTelegramUpdate(text="Team is short-staffed that week")
    await route(comment_update, deps, registry)

    assert approvals.decide_calls[0] == {
        "telegram_user_id": 42,
        "approval_request_id": "req-1",
        "decision": "reject",
        "comments": "Team is short-staffed that week",
    }
