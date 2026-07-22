"""Unit tests for formatting/keyboards.py — Reply/Inline keyboard builders,
including proof that the main menu is built FROM the command registry."""
from __future__ import annotations

from src.formatting.keyboards import (
    build_main_menu_keyboard,
    build_profile_actions_keyboard,
    build_unlink_confirmation_keyboard,
    remove_keyboard,
)
from src.handlers.registry import CommandRegistry


def test_main_menu_keyboard_reflects_registered_menu_commands_only():
    registry = CommandRegistry()

    @registry.command("start")  # no menu_label
    async def handle_start(ctx):
        pass

    @registry.command("profile", menu_label="👤 My Profile", menu_order=10)
    async def handle_profile(ctx):
        pass

    keyboard = build_main_menu_keyboard(registry)

    assert keyboard["resize_keyboard"] is True
    labels = [button["text"] for row in keyboard["keyboard"] for button in row]
    assert labels == ["👤 My Profile"]


def test_main_menu_keyboard_orders_buttons_by_menu_order():
    registry = CommandRegistry()

    @registry.command("status", menu_label="📋 My Status", menu_order=20)
    async def handle_status(ctx):
        pass

    @registry.command("profile", menu_label="👤 My Profile", menu_order=10)
    async def handle_profile(ctx):
        pass

    keyboard = build_main_menu_keyboard(registry)
    labels = [button["text"] for row in keyboard["keyboard"] for button in row]
    assert labels == ["👤 My Profile", "📋 My Status"]


def test_profile_actions_keyboard_has_refresh_and_unlink_callbacks():
    keyboard = build_profile_actions_keyboard()
    callback_data_values = [button["callback_data"] for row in keyboard["inline_keyboard"] for button in row]
    assert "profile:refresh" in callback_data_values
    # Must be a callback that's actually registered somewhere (see
    # link_handler.py's `account:unlink_prompt`) — this used to be
    # "account:unlink_confirm", which nothing ever registered, so tapping
    # the button silently no-opped via update_router's unregistered-callback
    # fallback.
    assert "account:unlink_prompt" in callback_data_values


def test_unlink_confirmation_keyboard_has_confirm_and_cancel():
    keyboard = build_unlink_confirmation_keyboard()
    callback_data_values = [button["callback_data"] for row in keyboard["inline_keyboard"] for button in row]
    assert "account:unlink_confirmed" in callback_data_values
    assert "account:unlink_cancelled" in callback_data_values


def test_remove_keyboard_shape():
    assert remove_keyboard() == {"remove_keyboard": True}
