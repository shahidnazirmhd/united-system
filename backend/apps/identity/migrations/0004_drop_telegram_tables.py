"""Refactor: Employee & Telegram Authentication.

Reverses migration 0003_add_telegram_tables.py in full. Telegram linking is
no longer an Identity concept — employees using Telegram never get an
identity.User account or a JWT, so `identity_telegram_accounts` and
`identity_telegram_link_tokens` have no reason to exist. The equivalent
tables (EmployeeRecord's new telegram_* columns and a new
EmployeeLinkTokenRecord) are created in apps/employees's own migrations,
keyed by employee_id, not user_id.

Hand-written, same discipline as every other migration in this project.
Run `python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation that
infrastructure/models.py and this migration agree.
"""
from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("identity", "0003_add_telegram_tables"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="telegramaccountrecord",
            name="identity_telegram_tguid_idx",
        ),
        migrations.DeleteModel(
            name="TelegramLinkTokenRecord",
        ),
        migrations.DeleteModel(
            name="TelegramAccountRecord",
        ),
    ]
