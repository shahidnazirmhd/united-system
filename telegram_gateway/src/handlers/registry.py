"""Open/Closed command + callback registry — the concrete mechanism behind
the Phase 7 brief's "menu system open for future HR modules."

`update_router.py` is written once and never edited again when a new
command family (Leave, Attendance, Payroll, Approvals — per the roadmap in
HRMS_Architecture.md section 9) is added later: it only ever calls
`registry.dispatch(...)`. A new module adds its own `handlers/x_handlers.py`
file that imports this shared `registry` instance and decorates its
functions — that's the entire integration surface, matching
HRMS_Folder_Structure.md section 3.5's "one file per command family."

The main menu (`formatting/keyboards.py`) is built FROM this same registry
(`menu_entries()`) rather than maintained as a second, parallel list —
a command that doesn't register a menu entry simply doesn't appear in the
menu (e.g. /start, which only makes sense as a first message, not a
recurring menu button), avoiding the two lists ever drifting out of sync.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

HandlerFunc = Callable[["HandlerContext"], Awaitable[None]]


@dataclass(frozen=True)
class MenuEntry:
    label: str
    order: int


@dataclass(frozen=True)
class RegisteredHandler:
    name: str
    func: HandlerFunc
    menu_entry: MenuEntry | None = None


class CommandRegistry:
    """One instance, imported by every `handlers/*.py` file
    (`from src.handlers.registry import registry`) to register into —
    the classic "plugin registry" pattern, not a Django-style
    autodiscovery mechanism, since this service's handler set is small and
    explicit imports in `main.py` are enough to trigger registration
    (see main.py's docstring)."""

    def __init__(self) -> None:
        self._commands: dict[str, RegisteredHandler] = {}
        self._callbacks: dict[str, RegisteredHandler] = {}

    def command(
        self, name: str, *, menu_label: str | None = None, menu_order: int = 100
    ) -> Callable[[HandlerFunc], HandlerFunc]:
        """Registers a text command, e.g. `/start` -> name="start" (the
        leading slash is stripped by update_router before lookup)."""

        def decorator(func: HandlerFunc) -> HandlerFunc:
            menu_entry = MenuEntry(label=menu_label, order=menu_order) if menu_label else None
            self._commands[name] = RegisteredHandler(name=name, func=func, menu_entry=menu_entry)
            return func

        return decorator

    def callback(self, data: str) -> Callable[[HandlerFunc], HandlerFunc]:
        """Registers an inline-keyboard callback_data handler, e.g.
        "menu:profile" -> the exact string a button's callback_data carries."""

        def decorator(func: HandlerFunc) -> HandlerFunc:
            self._callbacks[data] = RegisteredHandler(name=data, func=func)
            return func

        return decorator

    def get_command(self, name: str) -> RegisteredHandler | None:
        return self._commands.get(name)

    def get_command_by_menu_label(self, label: str) -> RegisteredHandler | None:
        """Reply Keyboard buttons (formatting/keyboards.py) arrive back as
        ordinary message text carrying the button's label, not a `/command`
        — this is how update_router.py maps a menu tap back to a
        registered command without a second, parallel label->command
        table."""
        for cmd in self._commands.values():
            if cmd.menu_entry is not None and cmd.menu_entry.label == label:
                return cmd
        return None

    def get_callback(self, data: str) -> RegisteredHandler | None:
        return self._callbacks.get(data)

    def menu_entries(self) -> list[tuple[str, MenuEntry]]:
        """(command_name, MenuEntry) pairs for every command that opted
        into appearing on the main menu, ordered by `menu_order` then
        `label` for a stable, deterministic layout."""
        entries = [(cmd.name, cmd.menu_entry) for cmd in self._commands.values() if cmd.menu_entry is not None]
        entries.sort(key=lambda pair: (pair[1].order, pair[1].label))
        return entries


registry = CommandRegistry()
