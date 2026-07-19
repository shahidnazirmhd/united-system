"""Production settings.

Fails loudly at startup rather than silently running insecurely if a
required secret was never configured — a missing SECRET_KEY should be a
deployment-time error, not a runtime vulnerability discovered later.
"""
from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

DEBUG = False

if not SECRET_KEY or SECRET_KEY.startswith("django-insecure"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a securely generated value in production. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
    )

if not ALLOWED_HOSTS or ALLOWED_HOSTS == ["*"]:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be explicitly set (not '*') in production.")

# HTTPS / transport security. SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE
# are currently inert (no session/CSRF-cookie-based auth is in use — see
# base.py's note on contrib.auth), kept set now so they're already correct
# the moment the Identity module or Django admin introduces cookie-based
# flows, rather than a setting someone has to remember to add later.
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
