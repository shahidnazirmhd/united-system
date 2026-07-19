"""ASGI entrypoint.

Kept available (not currently used by gunicorn/WSGI in this phase) so that
future async needs — e.g. websocket-based live notification push mentioned
in HRMS_Architecture.md section 4 flow C — don't require a later migration
off a WSGI-only setup.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_asgi_application()
