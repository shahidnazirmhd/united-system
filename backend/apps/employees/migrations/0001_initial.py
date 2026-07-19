"""Initial migration for the Employee module.

Hand-written, same reasoning and same discipline as
apps/identity/migrations/0001_initial.py: no PyPI/network/database access
in this sandbox to run `makemigrations` for real, so every field here was
cross-checked field-by-field against infrastructure/models.py. Run
`python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation.

Placed directly at `apps/employees/migrations/` — NOT nested under
`infrastructure/migrations/` — learned the hard way earlier in this
project's build: Django only auto-discovers migrations at
`<app_package>/migrations/`, following `AppConfig.name` (see
apps/employees/apps.py: `name = "apps.employees"`).

Circular-reference resolution (HRMS_Database_Design.md section 3.2, "the
well-known ordinary pattern for org-chart-shaped data"): DepartmentRecord is
created first without `head_employee`, EmployeeRecord is created next
(its `department` FK can now point at an existing table), then
`head_employee` is added to DepartmentRecord via a separate AddField once
EmployeeRecord exists.
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models

import shared_kernel.infrastructure.uuid7


def _base_fields() -> list[tuple[str, object]]:
    """The five fields every BaseModel-derived model carries
    (shared_kernel/infrastructure/base_models.py) — factored out so each
    CreateModel below can't drift from what BaseModel actually defines."""
    return [
        (
            "id",
            models.UUIDField(
                default=shared_kernel.infrastructure.uuid7.generate_uuid7,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        ("created_at", models.DateTimeField(auto_now_add=True)),
        ("updated_at", models.DateTimeField(auto_now=True)),
        ("created_by", models.UUIDField(blank=True, null=True)),
        ("updated_by", models.UUIDField(blank=True, null=True)),
    ]


def _soft_delete_fields() -> list[tuple[str, object]]:
    """The three fields SoftDeleteModel adds — only EmployeeRecord opts
    into this mixin (see infrastructure/models.py's docstring on why it is
    not part of BaseModel itself)."""
    return [
        ("is_deleted", models.BooleanField(default=False)),
        ("deleted_at", models.DateTimeField(blank=True, null=True)),
        ("deleted_by", models.UUIDField(blank=True, null=True)),
    ]


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DepartmentRecord",
            fields=[
                *_base_fields(),
                ("name", models.CharField(max_length=150)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "parent_department",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="child_departments",
                        to="employees.departmentrecord",
                    ),
                ),
            ],
            options={"db_table": "employees_departments"},
        ),
        migrations.CreateModel(
            name="EmployeeRecord",
            fields=[
                *_base_fields(),
                *_soft_delete_fields(),
                ("employee_code", models.CharField(max_length=20, unique=True)),
                ("user_id", models.UUIDField(blank=True, null=True, unique=True)),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("gender", models.CharField(blank=True, max_length=30, null=True)),
                ("work_email", models.EmailField(max_length=255, unique=True)),
                ("personal_email", models.EmailField(blank=True, max_length=255, null=True)),
                ("phone_number", models.CharField(blank=True, max_length=20, null=True)),
                ("date_of_joining", models.DateField()),
                ("termination_date", models.DateField(blank=True, null=True)),
                (
                    "employment_status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("on_leave", "On Leave"),
                            ("suspended", "Suspended"),
                            ("terminated", "Terminated"),
                        ],
                        default="active",
                        max_length=20,
                    ),
                ),
                (
                    "employment_type",
                    models.CharField(
                        choices=[
                            ("full_time", "Full Time"),
                            ("part_time", "Part Time"),
                            ("contract", "Contract"),
                            ("intern", "Intern"),
                        ],
                        max_length=20,
                    ),
                ),
                ("job_title", models.CharField(max_length=150)),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name="employees",
                        to="employees.departmentrecord",
                    ),
                ),
                (
                    "manager",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="direct_reports",
                        to="employees.employeerecord",
                    ),
                ),
            ],
            options={"db_table": "employees_employees"},
        ),
        migrations.AddField(
            model_name="departmentrecord",
            name="head_employee",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="headed_departments",
                to="employees.employeerecord",
            ),
        ),
        migrations.AddIndex(
            model_name="employeerecord",
            index=models.Index(fields=["employment_status"], name="employees_status_idx"),
        ),
        migrations.AddIndex(
            model_name="employeerecord",
            index=models.Index(fields=["department"], name="employees_department_idx"),
        ),
        migrations.AddConstraint(
            model_name="employeerecord",
            constraint=models.CheckConstraint(
                check=models.Q(("termination_date__isnull", True))
                | models.Q(("termination_date__gte", models.F("date_of_joining"))),
                name="employees_termination_after_joining",
            ),
        ),
        migrations.RunSQL(
            sql="CREATE SEQUENCE IF NOT EXISTS employees_employee_code_seq START WITH 1 INCREMENT BY 1;",
            reverse_sql="DROP SEQUENCE IF EXISTS employees_employee_code_seq;",
        ),
    ]
