"""Unit tests for handlers/registry.py — the Open/Closed command dispatch
table every handler and the main menu are built from."""
from __future__ import annotations

from src.handlers.registry import CommandRegistry


def test_command_registers_and_resolves_by_name():
    registry = CommandRegistry()

    @registry.command("ping")
    async def handle_ping(ctx):
        return "pong"

    resolved = registry.get_command("ping")
    assert resolved is not None
    assert resolved.name == "ping"
    assert resolved.func is handle_ping


def test_unregistered_command_returns_none():
    registry = CommandRegistry()
    assert registry.get_command("nonexistent") is None


def test_callback_registers_and_resolves_by_exact_data():
    registry = CommandRegistry()

    @registry.callback("menu:profile")
    async def handle_profile_callback(ctx):
        pass

    assert registry.get_callback("menu:profile") is not None
    assert registry.get_callback("menu:other") is None


def test_menu_entries_only_include_commands_with_menu_label():
    registry = CommandRegistry()

    @registry.command("start")  # no menu_label — should not appear
    async def handle_start(ctx):
        pass

    @registry.command("profile", menu_label="👤 My Profile", menu_order=10)
    async def handle_profile(ctx):
        pass

    @registry.command("status", menu_label="📋 My Status", menu_order=20)
    async def handle_status(ctx):
        pass

    entries = registry.menu_entries()
    names = [name for name, _ in entries]

    assert "start" not in names
    assert names == ["profile", "status"]  # ordered by menu_order


def test_menu_entries_are_ordered_by_menu_order_then_label():
    registry = CommandRegistry()

    @registry.command("z_cmd", menu_label="Z Button", menu_order=5)
    async def handle_z(ctx):
        pass

    @registry.command("a_cmd", menu_label="A Button", menu_order=5)
    async def handle_a(ctx):
        pass

    @registry.command("b_cmd", menu_label="B Button", menu_order=1)
    async def handle_b(ctx):
        pass

    entries = registry.menu_entries()
    names = [name for name, _ in entries]

    assert names == ["b_cmd", "a_cmd", "z_cmd"]


def test_get_command_by_menu_label_finds_the_registering_command():
    registry = CommandRegistry()

    @registry.command("profile", menu_label="👤 My Profile", menu_order=10)
    async def handle_profile(ctx):
        pass

    found = registry.get_command_by_menu_label("👤 My Profile")
    assert found is not None
    assert found.name == "profile"
    assert registry.get_command_by_menu_label("Not A Real Button") is None


def test_callback_prefix_matches_dynamic_suffix():
    registry = CommandRegistry()

    @registry.callback_prefix("leave:apply:type:")
    async def handle_type_selected(ctx):
        pass

    resolved = registry.get_callback("leave:apply:type:018f1234-5678-abcd")
    assert resolved is not None
    assert resolved.func is handle_type_selected
    assert registry.get_callback("leave:cancel:select:018f1234") is None


def test_exact_callback_takes_priority_over_a_matching_prefix():
    registry = CommandRegistry()

    @registry.callback_prefix("leave:apply:")
    async def handle_prefix(ctx):
        pass

    @registry.callback("leave:apply:abort")
    async def handle_exact(ctx):
        pass

    resolved = registry.get_callback("leave:apply:abort")
    assert resolved.func is handle_exact


def test_longest_matching_prefix_wins_when_multiple_match():
    registry = CommandRegistry()

    @registry.callback_prefix("leave:")
    async def handle_general(ctx):
        pass

    @registry.callback_prefix("leave:cancel:select:")
    async def handle_specific(ctx):
        pass

    resolved = registry.get_callback("leave:cancel:select:018f1234")
    assert resolved.func is handle_specific


def test_a_new_module_extends_the_menu_without_touching_existing_registrations():
    """The Open/Closed proof: registering a brand-new command (simulating a
    future Leave module) never requires modifying any existing registration
    or the registry class itself."""
    registry = CommandRegistry()

    @registry.command("profile", menu_label="👤 My Profile", menu_order=10)
    async def handle_profile(ctx):
        pass

    assert len(registry.menu_entries()) == 1

    @registry.command("leave_balance", menu_label="🌴 Leave Balance", menu_order=30)
    async def handle_leave_balance(ctx):
        pass

    entries = registry.menu_entries()
    assert len(entries) == 2
    assert [name for name, _ in entries] == ["profile", "leave_balance"]
