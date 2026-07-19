"""Telegram registration error-handling hardening (post-milestone review).

Adds `EmployeeLinkTokenRecord.attempt_count` — the brute-force guard behind
`TooManyOTPAttemptsError` (see domain/entities.py EmployeeLinkToken and
application/services/employee_telegram_linking_service.py's
MAX_OTP_ATTEMPTS) — plus a composite index on (telegram_user_id, chat_id),
the exact shape `get_pending_by_chat` queries by
(infrastructure/repositories.py).

Hand-written, same discipline as every other migration in this project. Run
`python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation that
infrastructure/models.py and this migration agree.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0004_add_telegram_linking"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeelinktokenrecord",
            name="attempt_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddIndex(
            model_name="employeelinktokenrecord",
            index=models.Index(
                fields=["telegram_user_id", "chat_id"], name="employees_link_tok_chat_idx"
            ),
        ),
    ]
