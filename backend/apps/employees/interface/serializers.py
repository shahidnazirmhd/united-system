"""DRF serializers for Employees.

Pure protocol translation (JSON <-> application-layer DTOs), no business
validation — matching Identity's interface/serializers.py convention and
its documented reasoning exactly (see that file's docstring).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.employees.domain.enums import EmployeeStatus, EmploymentType
from shared_kernel.api.fields import OptionalDateField, OptionalUUIDField


class CreateEmployeeSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    date_of_birth = OptionalDateField(required=False, allow_null=True, default=None)
    gender = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    work_email = serializers.EmailField()
    personal_email = serializers.EmailField(required=False, allow_null=True, allow_blank=True, default=None)
    phone_number = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=20, default=None
    )
    department_id = serializers.UUIDField()
    manager_id = OptionalUUIDField(required=False, allow_null=True, default=None)
    job_title = serializers.CharField(max_length=150)
    employment_type = serializers.ChoiceField(choices=EmploymentType.values())
    date_of_joining = serializers.DateField()
    user_id = OptionalUUIDField(required=False, allow_null=True, default=None)


class UpdateEmployeeSerializer(serializers.Serializer):
    """A full-replace update bound to the HTTP PATCH verb for a single,
    simpler endpoint — every field below is required, this is not true
    partial-patch semantics. Building field-level partial update (only
    change what's sent) is more machinery than this phase's brief asks for;
    revisit if a real need for partial updates shows up."""

    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    date_of_birth = OptionalDateField(required=False, allow_null=True, default=None)
    gender = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    work_email = serializers.EmailField()
    personal_email = serializers.EmailField(required=False, allow_null=True, allow_blank=True, default=None)
    phone_number = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=20, default=None
    )
    department_id = serializers.UUIDField()
    manager_id = OptionalUUIDField(required=False, allow_null=True, default=None)
    job_title = serializers.CharField(max_length=150)
    employment_type = serializers.ChoiceField(choices=EmploymentType.values())
    date_of_joining = serializers.DateField()
    termination_date = OptionalDateField(required=False, allow_null=True, default=None)


class EmployeeResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    employee_code = serializers.CharField()
    user_id = serializers.UUIDField(allow_null=True)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    full_name = serializers.CharField()
    date_of_birth = serializers.DateField(allow_null=True)
    gender = serializers.CharField(allow_null=True)
    work_email = serializers.EmailField()
    personal_email = serializers.EmailField(allow_null=True)
    phone_number = serializers.CharField(allow_null=True)
    department_id = serializers.UUIDField()
    manager_id = serializers.UUIDField(allow_null=True)
    job_title = serializers.CharField()
    employment_type = serializers.ChoiceField(choices=EmploymentType.values())
    date_of_joining = serializers.DateField()
    termination_date = serializers.DateField(allow_null=True)
    status = serializers.ChoiceField(choices=EmployeeStatus.values())
    # Resolved on single-record reads only (get, me) — null on list/search.
    # See EmployeeQueryService's docstring.
    department_name = serializers.CharField(allow_null=True)
    manager_name = serializers.CharField(allow_null=True)
    is_linked_to_telegram = serializers.BooleanField()
    telegram_username = serializers.CharField(allow_null=True)
    telegram_linked_at = serializers.DateTimeField(allow_null=True)


# --- Telegram linking (Employee & Telegram Authentication refactor) ------
# Called only by the Telegram Gateway (a trusted server-side client
# authenticated via shared_kernel.api.permissions.HasInternalServiceKey),
# never directly by an end user's browser — see TELEGRAM_GATEWAY.md.


class RequestEmployeeTelegramLinkSerializer(serializers.Serializer):
    employee_code = serializers.CharField(max_length=20)
    telegram_user_id = serializers.IntegerField()
    chat_id = serializers.IntegerField()
    telegram_username = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class VerifyEmployeeTelegramLinkSerializer(serializers.Serializer):
    telegram_user_id = serializers.IntegerField()
    chat_id = serializers.IntegerField()
    otp = serializers.CharField(min_length=6, max_length=6)
    telegram_username = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)


class TelegramUserIdQuerySerializer(serializers.Serializer):
    """Shared query-param shape for the GET endpoints below — both need
    exactly one input, `telegram_user_id`, the Gateway-supplied identifier
    for the Telegram user making the request."""

    telegram_user_id = serializers.IntegerField()


class EmployeeTelegramLinkStatusSerializer(serializers.Serializer):
    is_linked = serializers.BooleanField()
    telegram_username = serializers.CharField(allow_null=True)
    linked_at = serializers.DateTimeField(allow_null=True)
