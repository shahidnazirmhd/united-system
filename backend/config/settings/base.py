"""Base settings shared by every environment.

Environment-specific files (local.py, staging.py, production.py, test.py)
import everything from here with `from .base import *` and override only
what genuinely differs per environment — see HRMS_Folder_Structure.md
section 1.1.
"""
from __future__ import annotations

from pathlib import Path

import environ

from config.module_registry import ACTIVE_MODULES

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# BASE_DIR = backend/ (this file is backend/config/settings/base.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
# PROJECT_ROOT = repository root, one level above backend/ — this is where
# the single shared .env file lives, next to infra/docker-compose.yml, so
# both Django (run directly) and docker-compose read the exact same file.
PROJECT_ROOT = BASE_DIR.parent

# --------------------------------------------------------------------------
# Environment variables
# --------------------------------------------------------------------------
env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(str(PROJECT_ROOT / ".env"))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-placeholder-do-not-use-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Every real deployment of this app sits behind a reverse proxy/load balancer
# that terminates TLS itself and forwards plain HTTP to the container (Render,
# Railway, Fly, nginx, ... — this is the norm, not a Render-specific quirk).
# Without this, Django has no way to know the original request was HTTPS, so
# staging.py/production.py's SECURE_SSL_REDIRECT=True would see every
# proxied request as insecure and issue an HTTPS redirect... to itself,
# forever. Harmless in local dev (runserver has no proxy in front of it, so
# this header is simply never present) and in tests (same reason).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
# `django.contrib.auth`, `.admin`, and `.sessions` are deliberately NOT
# installed yet. This project authenticates exclusively via JWT (issued by
# the future Identity module) and never uses Django's session/cookie auth or
# admin site in this phase. Installing contrib.auth now would force a
# decision about AUTH_USER_MODEL that belongs to the Identity module — and
# Django's own rule ("never change AUTH_USER_MODEL after your first
# migration") makes committing to a throwaway placeholder now actively
# risky rather than neutral. See the explanation accompanying this phase's
# delivery for the full reasoning.
DJANGO_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
]

# Fed entirely by the module registry — this list is intentionally not
# hand-maintained here, see config/module_registry.py.
LOCAL_APPS = list(ACTIVE_MODULES)

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Assigns/propagates the request correlation id before anything else
    # runs, so every subsequent middleware and view can rely on it already
    # being set (shared_kernel/middleware/request_id.py — also the source
    # of audit_log.request_id, HRMS_Database_Design.md section 4).
    "shared_kernel.middleware.request_id.RequestIDMiddleware",
    "shared_kernel.middleware.request_logging.RequestLoggingMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.gzip.GZipMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Database (PostgreSQL)
# --------------------------------------------------------------------------
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
# CONN_MAX_AGE defaults to 0 (no persistent connections at the Django level)
# because production sits behind PgBouncer in transaction-pooling mode
# (HRMS_Architecture.md section 8) — Django-level connection persistence
# and PgBouncer transaction pooling actively fight each other. Raise this
# only if/when PgBouncer is configured in session-pooling mode instead.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=0)
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"]["sslmode"] = env("DB_SSL_MODE", default="prefer")

# Transactions are managed explicitly per use case via
# shared_kernel.infrastructure.django_unit_of_work.DjangoUnitOfWork, not by
# Django's default per-request wrapping. This is what lets the identical use
# case run correctly whether it's invoked from a DRF view, a Celery task, or
# a future management command — none of which share an HTTP request/response
# cycle to hang an implicit transaction boundary off of.
ATOMIC_REQUESTS = False

# --------------------------------------------------------------------------
# Internationalization
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Static files
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --------------------------------------------------------------------------
# Redis — three distinct roles (HRMS_Architecture.md section 8), plus a
# fourth logical DB reserved for the Identity module's token blocklist.
# Each is independently configurable/splittable to its own Redis instance
# later without touching application code, since every consumer reads its
# own env var rather than assuming a shared connection.
# --------------------------------------------------------------------------
REDIS_CACHE_URL = env("REDIS_CACHE_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/2")
# Reserved for the Identity module's JWT revocation denylist — not consumed
# by any code yet in this phase, declared now so the env var contract is
# stable before that module needs it.
REDIS_TOKEN_BLOCKLIST_URL = env("REDIS_TOKEN_BLOCKLIST_URL", default="redis://localhost:6379/3")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_CACHE_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# --------------------------------------------------------------------------
# Celery
# --------------------------------------------------------------------------
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# Tasks are only acknowledged after they complete, not on receipt — a worker
# crash mid-task re-delivers the task instead of silently losing it. This
# matters more here than in most systems: payroll runs and notification
# sends (future modules) are exactly the kind of task that must not vanish.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int("CELERY_WORKER_PREFETCH_MULTIPLIER", default=1)
CELERY_TASK_DEFAULT_QUEUE = "default"

# --------------------------------------------------------------------------
# JWT (Identity module)
#
# Signed with a dedicated key rather than reusing SECRET_KEY, so the two can
# be rotated independently — rotating SECRET_KEY (used for other Django
# cryptographic signing) would otherwise silently invalidate every issued
# JWT too. Defaults to SECRET_KEY only as a local-dev convenience; set
# JWT_SIGNING_KEY explicitly in staging/production.
# --------------------------------------------------------------------------
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY", default=SECRET_KEY)
JWT_ALGORITHM = env("JWT_ALGORITHM", default="HS256")
JWT_ACCESS_TOKEN_LIFETIME_MINUTES = env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)
JWT_REFRESH_TOKEN_LIFETIME_DAYS = env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=7)

# --------------------------------------------------------------------------
# SMTP (shared_kernel.infrastructure.email_client) — Employee & Telegram
# Authentication refactor.
#
# Read directly by each module's composition root (e.g.
# apps/employees/interface/dependencies.py), which constructs a
# SmtpEmailClient from these values, or falls back to LoggingEmailClient
# when SMTP_HOST is unset (local dev with no mail provider configured at
# all). Never hardcode credentials — see .env.example for the full variable
# list and a step-by-step guide to configuring a temporary Gmail account
# for local development/testing.
# --------------------------------------------------------------------------
SMTP_HOST = env("SMTP_HOST", default="")
SMTP_PORT = env.int("SMTP_PORT", default=587)
SMTP_USERNAME = env("SMTP_USERNAME", default="")
SMTP_PASSWORD = env("SMTP_PASSWORD", default="")
SMTP_USE_TLS = env.bool("SMTP_USE_TLS", default=True)
SMTP_FROM_EMAIL = env("SMTP_FROM_EMAIL", default="no-reply@united-hrms.local")
# Display name only ("United HRMS" <address>) — deliverability, not identity:
# a bare email address with no display name is one of several free, easy
# spam signals (see SmtpEmailClient.send()'s docstring for the others).
SMTP_FROM_NAME = env("SMTP_FROM_NAME", default="United HRMS")
SMTP_TIMEOUT_SECONDS = env.int("SMTP_TIMEOUT_SECONDS", default=10)

# --------------------------------------------------------------------------
# Internal service authentication (shared_kernel.api.permissions.
# HasInternalServiceKey) — Employee & Telegram Authentication refactor.
#
# A static shared secret the Telegram Gateway presents (as the
# X-Internal-Service-Key header) when calling backend endpoints on behalf
# of an employee who has no JWT of their own. Deliberately left with no
# default: an empty/missing key must fail every HasInternalServiceKey check
# closed, never open, so a misconfigured environment is loud (401s) rather
# than silently trusting any caller.
# --------------------------------------------------------------------------
INTERNAL_SERVICE_API_KEY = env("INTERNAL_SERVICE_API_KEY", default="")

# --------------------------------------------------------------------------
# Leave module (Phase 8)
#
# Whether Apply Leave accepts a start_date in the past. Defaults to False —
# most HR policies require leave to be requested in advance; the rare
# legitimate exception (retroactively recording an already-taken absence)
# is an environment-level policy choice, not something every request should
# be able to opt into individually, so it's a setting rather than a
# per-request flag.
# --------------------------------------------------------------------------
LEAVE_ALLOW_PAST_START_DATE = env.bool("LEAVE_ALLOW_PAST_START_DATE", default=False)

# --------------------------------------------------------------------------
# Approval Engine (Phase 9)
#
# The backend->Gateway call direction is new as of this module: every prior
# integration was Gateway->backend only (the Gateway is a first-party HTTP
# client of this API). Sending an unsolicited Telegram notification the
# moment an approval request needs a decision requires the reverse — a
# Celery task (apps/approvals/infrastructure/tasks.py) calls the Gateway's
# own `POST /internal/notify`, authenticated with the exact same
# INTERNAL_SERVICE_API_KEY defined above (the same static shared secret
# already proves "this caller is trusted" in the other direction; reusing
# it here rather than minting a second secret keeps exactly one credential
# to rotate). Left with no default for the same "fail loud, not open"
# reasoning INTERNAL_SERVICE_API_KEY documents above.
# --------------------------------------------------------------------------
TELEGRAM_GATEWAY_BASE_URL = env("TELEGRAM_GATEWAY_BASE_URL", default="")
TELEGRAM_GATEWAY_NOTIFY_TIMEOUT_SECONDS = env.int("TELEGRAM_GATEWAY_NOTIFY_TIMEOUT_SECONDS", default=10)

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.identity.interface.authentication.JWTAuthentication",
    ],
    # With no authentication classes configured, DRF falls back to this for
    # unauthenticated requests. Explicitly None (rather than the DRF default
    # of django.contrib.auth.models.AnonymousUser) because that default
    # would import a Model class from an app that isn't in INSTALLED_APPS,
    # which raises at import time. IsAuthenticated correctly treats
    # request.user = None as "not authenticated" with no error.
    "UNAUTHENTICATED_USER": None,
    "EXCEPTION_HANDLER": "shared_kernel.api.exception_handler.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "shared_kernel.api.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "shared_kernel.api.throttling.StandardUserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "standard": "120/min",
        "auth": "10/min",
        # OTP requests/verification specifically — tighter than "auth"
        # because a brute-forced 6-digit OTP is a meaningfully weaker
        # secret than a real password if left unthrottled. Reused by
        # apps.employees's own Telegram-linking endpoints (Employee &
        # Telegram Authentication refactor) — this throttle class lives in
        # shared_kernel precisely so it isn't tied to any one module.
        "telegram": "10/min",
    },
}

# The browsable HTML API is convenient in development and a needless
# surface/asset in production, where DEBUG is False.
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (
    [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ]
    if DEBUG
    else ["rest_framework.renderers.JSONRenderer"]
)

SPECTACULAR_SETTINGS = {
    "TITLE": "United HRMS API",
    "DESCRIPTION": "Enterprise HR Management System backend API.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# --------------------------------------------------------------------------
# Logging — console/stdout only, deliberately no file handler.
#
# Containers should treat logs as an event stream to stdout/stderr and let
# the surrounding platform (Docker, Kubernetes) collect and ship them; a
# file handler inside the container just adds a volume/rotation problem
# nothing here needs to own. LOG_FORMAT switches between a human-readable
# formatter (local dev) and structured JSON (staging/production, where log
# aggregation tooling expects it).
# --------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_FORMAT = env("LOG_FORMAT", default="verbose")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s %(module)s :: %(message)s",
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(module)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "shared_kernel": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

APP_VERSION = env("APP_VERSION", default="0.1.0")

# --------------------------------------------------------------------------
# API versioning
#
# See shared_kernel/domain/constants.py:API_VERSION for why this is a named
# constant rather than DRF's full URLPathVersioning machinery: one version
# exists today, and building version-negotiation infrastructure for a
# single version is complexity with no current payoff. config/urls.py
# builds the `/api/{API_VERSION}/` prefix from this constant.
# --------------------------------------------------------------------------
from shared_kernel.domain.constants import API_VERSION  # noqa: E402
