"""Round 15 item 9 — renames `EmployeeRecord.termination_date` to
`last_working_date` (used for both resignation and termination cases; see
domain/value_objects.py's `EmploymentInformation` docstring). The check
constraint tying it to `date_of_joining` is dropped and re-added under a
matching new name since Django's migration framework does not auto-rename
constraints when the fields they reference are renamed.

Hand-written, same discipline as every other migration in this project.
Run `python manage.py makemigrations --check` after pulling this into an
environment with dependencies installed, as a final confirmation that
infrastructure/models.py and this migration agree.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0006_add_employee_current_status"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="employeerecord",
            name="employees_termination_after_joining",
        ),
        migrations.RenameField(
            model_name="employeerecord",
            old_name="termination_date",
            new_name="last_working_date",
        ),
        migrations.AddConstraint(
            model_name="employeerecord",
            constraint=models.CheckConstraint(
                check=models.Q(last_working_date__isnull=True)
                | models.Q(last_working_date__gte=models.F("date_of_joining")),
                name="employees_last_working_date_after_joining",
            ),
        ),
    ]
