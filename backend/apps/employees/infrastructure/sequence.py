"""Race-safe `employee_code` generation via a real Postgres sequence.

A row-count-based scheme (`EmployeeRecord.objects.count() + 1`) was
rejected: it's not safe under concurrent creates (two requests can read the
same count before either commits), and it silently breaks the moment any
row is soft-deleted (count() no longer reflects "how many employee codes
have ever been issued"). A Postgres `SEQUENCE` is the standard, race-free
primitive for a monotonic counter independent of table row count —
`nextval()` is atomic at the database level regardless of concurrent
callers or transaction isolation.

The sequence itself (`employees_employee_code_seq`) is created by
migrations/0001_initial.py via `RunSQL`, with a matching reverse operation
for reversibility.
"""
from __future__ import annotations

from django.db import connection

SEQUENCE_NAME = "employees_employee_code_seq"
CODE_PREFIX = "EMP-"
CODE_DIGITS = 6


def next_employee_code() -> str:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT nextval('{SEQUENCE_NAME}')")
        (next_value,) = cursor.fetchone()
    return f"{CODE_PREFIX}{next_value:0{CODE_DIGITS}d}"
