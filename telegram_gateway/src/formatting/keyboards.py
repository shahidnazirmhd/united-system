"""Reusable Telegram UI components — Reply and Inline Keyboard builders.

Deliberately built FROM `handlers/registry.py`'s registered commands
(`build_main_menu_keyboard`) rather than a hand-maintained button list, so a
new module's handler file is the only place a future contributor touches to
add a menu item — see registry.py's docstring for the full reasoning.
"""
from __future__ import annotations

from typing import Any

from src.handlers.registry import CommandRegistry


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
            [{"text": "🔓 Unlink account", "callback_data": "account:unlink_confirm"}],
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
