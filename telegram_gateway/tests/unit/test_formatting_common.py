"""Unit tests for formatting/common.py."""
from __future__ import annotations

from src.formatting.common import escape_markdown, field_or_placeholder, format_status_label


def test_field_or_placeholder_returns_placeholder_for_none():
    assert field_or_placeholder(None) == "_Not available_"


def test_field_or_placeholder_returns_placeholder_for_blank_string():
    assert field_or_placeholder("   ") == "_Not available_"


def test_field_or_placeholder_returns_escaped_value_when_present():
    assert field_or_placeholder("Engineering") == "Engineering"


def test_escape_markdown_escapes_special_characters():
    assert escape_markdown("R&D_Team [Special]") == "R&D\\_Team \\[Special]"


def test_field_or_placeholder_escapes_underscores_in_real_values():
    assert field_or_placeholder("R&D_Team") == "R&D\\_Team"


def test_format_status_label_known_statuses():
    assert format_status_label("active") == "🟢 Active"
    assert format_status_label("suspended") == "🔴 Suspended"
    assert format_status_label("on_leave") == "🟡 On Leave"
    assert format_status_label("terminated") == "⚫ Terminated"


def test_format_status_label_unknown_status_falls_back_to_title_case():
    assert format_status_label("some_new_status") == "Some New Status"
