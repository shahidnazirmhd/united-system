"""Data migration: seeds a small set of starter departments.

Bootstrap necessity, same category as
apps/identity/migrations/0002_seed_system_roles.py: `Department` has no
create endpoint this phase (see infrastructure/models.py's docstring on why
— it's a minimal supporting table for Employee's FK, not a full module),
which means without this migration there would be no way to create the
first department at all, and therefore no way to create the first employee
either. Fetch a seeded department's id with:

    docker compose -f infra/docker-compose.yml --env-file .env exec backend \\
      python manage.py shell -c "from apps.employees.infrastructure.models import DepartmentRecord; \\
      [print(d.code, d.id) for d in DepartmentRecord.objects.all()]"

Reversible: the reverse migration removes exactly what forward created.
"""
from __future__ import annotations

from django.db import migrations

DEFAULT_DEPARTMENTS = [
    {"name": "General", "code": "GEN"},
    {"name": "Engineering", "code": "ENG"},
    {"name": "Human Resources", "code": "HR"},
]


def seed_default_departments(apps, schema_editor):
    DepartmentRecord = apps.get_model("employees", "DepartmentRecord")
    for dept in DEFAULT_DEPARTMENTS:
        DepartmentRecord.objects.get_or_create(code=dept["code"], defaults={"name": dept["name"]})


def remove_default_departments(apps, schema_editor):
    DepartmentRecord = apps.get_model("employees", "DepartmentRecord")
    DepartmentRecord.objects.filter(code__in=[d["code"] for d in DEFAULT_DEPARTMENTS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0002_seed_employee_permissions"),
    ]

    operations = [
        migrations.RunPython(seed_default_departments, remove_default_departments),
    ]
