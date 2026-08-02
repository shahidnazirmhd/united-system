"""Reusable Telegram UI components — Reply and Inline Keyboard builders.

Deliberately built FROM `handlers/registry.py`'s registered commands
(`build_main_menu_keyboard`) rather than a hand-maintained button list, so a
new module's handler file is the only place a future contributor touches to
add a menu item — see registry.py's docstring for the full reasoning.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.handlers.registry import CommandRegistry

if TYPE_CHECKING:
    from src.api_client.endpoints.leave import LeaveRequest, LeaveType


def build_main_menu_keyboard(registry: CommandRegistry) -> dict[str, Any]:
    """A persistent Reply Keyboard (shown in place of the phone's own
    keyboard) — the "professional Telegram menu system" the brief asks for.
    Each button's text is the literal command's menu label; Telegram sends
    that label back as ordinary message text when tapped, which
    `webhook/update_router.py` maps back to the command via
    `registry.get_command_by_menu_label` (see that module)."""
    entries = registry.menu_entries()
    rows = [[{"text": label}] for _, entry in entries for label in [entry.label]]
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


def build_profile_actions_keyboard() -> dict[str, Any]:
    """Inline keyboard attached to the "My Profile" card — actions that
    apply to that specific message, not the whole chat, hence inline rather
    than the persistent reply keyboard."""
    return {
        "inline_keyboard": [
            [{"text": "🔄 Refresh", "callback_data": "profile:refresh"}],
            [{"text": "🔓 Unlink account", "callback_data": "account:unlink_prompt"}],
        ]
    }


def build_unlink_confirmation_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Yes, unlink", "callback_data": "account:unlink_confirmed"},
                {"text": "❌ Cancel", "callback_data": "account:unlink_cancelled"},
            ]
        ]
    }


def remove_keyboard() -> dict[str, Any]:
    return {"remove_keyboard": True}


# --- Leave (Phase 8) ------------------------------------------------------
# Callback data for these uses `registry.callback_prefix()` (see that
# method's docstring) since a leave type id / leave request id is chosen at
# render time, not known ahead of time the way `profile:refresh` is.


#: Telegram inline button text is limited to 64 characters — labels built
#: from employee/leave-type data are truncated defensively rather than
#: risking a rejected sendMessage call for an unusually long leave type
#: name or a multi-line summary.
_MAX_BUTTON_TEXT_LENGTH = 64


def _truncate_button_text(text: str) -> str:
    if len(text) <= _MAX_BUTTON_TEXT_LENGTH:
        return text
    return text[: _MAX_BUTTON_TEXT_LENGTH - 1] + "…"


def build_leave_type_selection_keyboard(leave_types: list[LeaveType]) -> dict[str, Any]:
    from src.formatting.leave_formatter import format_leave_type_button_label

    rows = [
        [{"text": _truncate_button_text(format_leave_type_button_label(lt)), "callback_data": f"leave:apply:type:{lt.id}"}]
        for lt in leave_types
    ]
    rows.append([{"text": "❌ Cancel", "callback_data": "leave:apply:abort"}])
    return {"inline_keyboard": rows}


def build_apply_leave_confirm_keyboard() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Submit", "callback_data": "leave:apply:confirm"},
                {"text": "❌ Cancel", "callback_data": "leave:apply:abort"},
            ]
        ]
    }


def build_leave_request_selection_keyboard(requests: list[LeaveRequest]) -> dict[str, Any]:
    from src.formatting.leave_formatter import format_leave_request_summary_line

    rows = [
        [{"text": _truncate_button_text(format_leave_request_summary_line(r)), "callback_data": f"leave:cancel:select:{r.id}"}]
        for r in requests
    ]
    rows.append([{"text": "❌ Never mind", "callback_data": "leave:cancel:abort"}])
    return {"inline_keyboard": rows}


def build_cancel_leave_confirm_keyboard(leave_request_id: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Yes, cancel it", "callback_data": f"leave:cancel:confirm:{leave_request_id}"},
                {"text": "❌ Never mind", "callback_data": "leave:cancel:abort"},
            ]
        ]
    }


# --- Approval Engine (Phase 9) --------------------------------------------
# Callback data uses `registry.callback_prefix()` (see that method's
# docstring) since an approval request id is chosen at render time, not
# known ahead of time.


def build_approval_decision_keyboard(approval_request_id: str) -> dict[str, Any]:
    """Attached to every "you have a decision to make" message — the
    unsolicited push notification (`handlers/approval_handlers.py`'s
    `POST /internal/notify` handler) and each per-item message
    `/pending_approvals` sends both use this same keyboard."""
    return {
        "inline_keyboard": [
            [
                {"text": "✅ Approve", "callback_data": f"approval:decide:approve:{approval_request_id}"},
                {"text": "❌ Reject", "callback_data": f"approval:decide:reject:{approval_request_id}"},
            ]
        ]
    }
