"""Unit tests for formatting/profile_formatter.py — the "My Profile" and
"Employee Status" text builders."""
from __future__ import annotations

from src.api_client.endpoints.employees import EmployeeProfile
from src.formatting.profile_formatter import format_employee_status, format_my_profile


def _profile(**overrides) -> EmployeeProfile:
    defaults = dict(
        id="11111111-1111-1111-1111-111111111111",
        employee_code="E000123",
        full_name="Ada Lovelace",
        job_title="Software Engineer",
        work_email="ada.lovelace@example.com",
        phone_number="+1-555-0100",
        department_name="Engineering",
        manager_name="Charles Babbage",
        employment_type="full_time",
        date_of_joining="2024-01-15",
        status="active",
        # Round 15 items 7/8 — see EmployeeProfile's own docstring comment.
        current_status="working",
        is_linked_to_telegram=True,
        telegram_username="ada",
    )
    defaults.update(overrides)
    return EmployeeProfile(**defaults)


def test_my_profile_includes_all_known_fields():
    text = format_my_profile(_profile())

    assert "Ada Lovelace" in text
    assert "E000123" in text
    assert "Software Engineer" in text
    assert "Engineering" in text
    assert "Charles Babbage" in text
    assert "ada.lovelace@example.com" in text
    assert "+1-555-0100" in text
    assert "2024-01-15" in text
    assert "Full Time" in text
    assert "🟢 Active" in text


def test_my_profile_shows_placeholder_for_missing_manager():
    text = format_my_profile(_profile(manager_name=None))
    assert "_Not available_" in text


def test_my_profile_shows_placeholder_for_company_and_branch():
    """Company/Branch have no home in the approved DB schema — see this
    module's docstring. Both must always render as the friendly
    placeholder, never be silently omitted."""
    text = format_my_profile(_profile())
    assert text.count("_Not available_") >= 2  # at least Company + Branch


def test_my_profile_escapes_markdown_in_name():
    text = format_my_profile(_profile(full_name="A_B Test"))
    assert "A\\_B Test" in text


def test_employee_status_is_concise_and_shows_status():
    text = format_employee_status(_profile(status="suspended"))
    assert "E000123" in text
    assert "🔴 Suspended" in text
    # The status view is deliberately terser than the full profile card —
    # it should not repeat department/manager/contact details.
    assert "Engineering" not in text
