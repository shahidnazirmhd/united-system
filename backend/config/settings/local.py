"""Local development settings — run outside or inside Docker via
docker-compose.yml (not docker-compose.prod.yml)."""
from __future__ import annotations

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Permissive CORS in local dev only — never in staging/production, where
# CORS_ALLOWED_ORIGINS (base.py, env-driven) is the actual allowlist.
CORS_ALLOW_ALL_ORIGINS = True
