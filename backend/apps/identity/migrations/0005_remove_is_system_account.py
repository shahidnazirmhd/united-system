"""Phase 12 bugfix: removes `UserRecord.is_system_account`.

Investigated during a bug report about the "System Account" toggle in the
User Management UI: the field was threaded end-to-end (model, domain entity,
DTOs, serializers, `AuthenticatedPrincipal`, list filter) but never actually
read anywhere to change behavior — no permission check, rate-limit
exemption, or business rule branched on it. Confirmed via a full-repo grep
before removing: zero conditionals on `.is_system_account` existed outside
of the code that merely carries the value through. Since it has no
functional purpose, it's removed entirely rather than left as a dead,
misleading toggle in the admin UI — see IDENTITY_API.md's updated User
Management section.

Hand-written, same discipline as every other migration in this project.
Run `python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation that
infrastructure/models.py and this migration agree.
"""
from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0004_drop_telegram_tables"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="userrecord",
            name="is_system_account",
        ),
    ]
