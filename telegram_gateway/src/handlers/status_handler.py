""""Employee Status" — a quick-glance view distinct from the full "My
Profile" card, per the Phase 7 brief. Reuses the same
`api_client/endpoints/employees.py` call (there is exactly one backend
endpoint for this data); only the formatter differs
(`formatting/profile_formatter.format_employee_status`).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.errors import GatewayError, friendly_message_for
from src.formatting.profile_formatter import format_employee_status
from src.handlers.registry import registry
from src.logging_config import log_event

if TYPE_CHECKING:
    from src.handlers.context import HandlerContext

logger = logging.getLogger(__name__)


@registry.command("status", menu_label="📋 My Status", menu_order=20)
async def handle_status(ctx: HandlerContext) -> None:
    try:
        profile = await ctx.employees.get_profile(telegram_user_id=ctx.telegram_user_id)
    except GatewayError as exc:
        log_event(logger, logging.INFO, "status_view_failed", telegram_user_id=ctx.telegram_user_id, error=str(exc))
        await ctx.reply(friendly_message_for(exc))
        return
    await ctx.reply(format_employee_status(profile))
