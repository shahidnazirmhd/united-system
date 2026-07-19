"""Environment-driven settings for the Telegram Gateway — nothing else.

Per HRMS_Folder_Structure.md section 3.7: "no HR configuration, since this
service has no HR concerns to configure." Every value here is either a
Telegram Bot API credential, the HRMS backend's base URL, or this service's
own Redis connection — never a database DSN, never an HR-domain constant.

Uses pydantic-settings so misconfiguration (a missing required env var) fails
loudly at process start, not on the first webhook call.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_GATEWAY_", env_file=".env", extra="ignore")

    # --- Telegram Bot API ---------------------------------------------
    bot_token: str = Field(..., description="Telegram Bot API token issued by @BotFather.")
    webhook_secret_token: str = Field(
        ..., description="Shared secret Telegram echoes back in X-Telegram-Bot-Api-Secret-Token on every "
        "webhook call — see webhook/security.py. Never logged, never returned in any response."
    )
    webhook_path: str = Field(
        default="/webhook/telegram", description="The path this service registers with Telegram via setWebhook."
    )

    # --- HRMS backend (the *only* HR data dependency) -------------------
    hrms_api_base_url: str = Field(..., description="Base URL of the Django backend, e.g. http://backend:8000")
    hrms_api_timeout_seconds: float = Field(default=10.0)
    internal_api_key: str = Field(
        ...,
        description="Static shared secret sent as X-Internal-Service-Key on every backend call — proves this "
        "service really is the Gateway (shared_kernel.api.permissions.HasInternalServiceKey on the Django side). "
        "Must match the backend's own INTERNAL_SERVICE_API_KEY exactly (see backend's .env.example). Employee & "
        "Telegram Authentication refactor: replaces the old per-employee JWT this service used to hold — there is "
        "no per-employee credential anymore, only this one service-wide secret.",
    )

    # --- This service's own datastore (never the HRMS database) ---------
    redis_url: str = Field(..., description="Redis instance owned by this service alone — the Gateway's own "
        "transient 'awaiting OTP' conversation state (auth/account_linking.py), nothing else. Distinct from the "
        "backend's own Redis (HRMS_Architecture.md section 3.4: 'explicitly not the HRMS database').")

    # --- Operational ------------------------------------------------------
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    rate_limit_per_chat_per_minute: int = Field(
        default=20, description="Soft per-chat throttle applied at the webhook layer, ahead of anything Telegram "
        "itself already flood-limits — see webhook/rate_limiter.py."
    )

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached — Settings() re-reads and re-validates the environment on every
    call otherwise, which is wasted work for values that never change during
    a process's lifetime. `get_settings.cache_clear()` in tests when a
    different environment needs to be simulated."""
    return Settings()
