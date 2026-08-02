"""DRF serializers for Employees.

Pure protocol translation (JSON <-> application-layer DTOs), no business
validation — matching Identity's interface/serializers.py convention and
its documented reasoning exactly (see that file's docstring).
"""
from __future__ import annotations

from rest_framework import serializers

from apps.employees.domain.enums import EmployeeCurrentStatus, EmployeeStatus, EmploymentType
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
    # Round 15 item 9 — renamed from termination_date; used for both
    # resignation and termination.
    last_working_date = OptionalDateField(required=False, allow_null=True, default=None)


class LinkUserToEmployeeSerializer(serializers.Serializer):
    """Phase 12 (User Management): body for POST /employees/{id}/link-user/."""

    user_id = serializers.UUIDField()


# --- Department CRUD (Phase 12) --------------------------------------------


class CreateDepartmentSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    code = serializers.CharField(max_length=20)
    parent_department_id = OptionalUUIDField(required=False, allow_null=True, default=None)
    head_employee_id = OptionalUUIDField(required=False, allow_null=True, default=None)


class UpdateDepartmentSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    code = serializers.CharField(max_length=20)
    parent_department_id = OptionalUUIDField(required=False, allow_null=True, default=None)
    head_employee_id = OptionalUUIDField(required=False, allow_null=True, default=None)
    is_active = serializers.BooleanField(default=True)


class DepartmentResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    code = serializers.CharField()
    parent_department_id = serializers.UUIDField(allow_null=True)
    head_employee_id = serializers.UUIDField(allow_null=True)
    is_active = serializers.BooleanField()
    # Resolved on single-record reads only (get) — null on list. See
    # DepartmentQueryService's docstring.
    parent_department_name = serializers.CharField(allow_null=True)
    head_employee_name = serializers.CharField(allow_null=True)


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
    last_working_date = serializers.DateField(allow_null=True)  # round 15 item 9
    status = serializers.ChoiceField(choices=EmployeeStatus.values())
    # Resolved on single-record reads only (get, me) — null on list/search.
    # See EmployeeQueryService's docstring.
    department_name = serializers.CharField(allow_null=True)
    manager_name = serializers.CharField(allow_null=True)
    # Phase 12 bugfix: the linked User's email, resolved the same way/same
    # scope as department_name/manager_name above.
    linked_user_email = serializers.CharField(allow_null=True)
    is_linked_to_telegram = serializers.BooleanField()
    telegram_username = serializers.CharField(allow_null=True)
    telegram_linked_at = serializers.DateTimeField(allow_null=True)
    # Round 14 item 8 — see domain/enums.py EmployeeCurrentStatus's
    # docstring for why this is separate from `status` above.
    current_status = serializers.ChoiceField(choices=EmployeeCurrentStatus.values())
    status_before_leave = serializers.ChoiceField(choices=EmployeeCurrentStatus.values(), allow_null=True)
    is_eligible_for_leave = serializers.BooleanField()


class UpdateEmployeeCurrentStatusSerializer(serializers.Serializer):
    """Round 14 item 8 — body for POST /employees/{id}/current-status/.
    Deliberately excludes SICK_LEAVE/ANNUAL_LEAVE from the choice list
    presented here — see `Employee.update_current_status_manually`'s
    docstring for why those two can never be chosen manually; the service
    layer still enforces this even if a client sends one anyway."""

    current_status = serializers.ChoiceField(
        choices=[
            (EmployeeCurrentStatus.NOT_JOINED.value, "Not Joined"),
            (EmployeeCurrentStatus.WORKING.value, "Working"),
            (EmployeeCurrentStatus.TERMINATED.value, "Terminated"),
            (EmployeeCurrentStatus.RESIGNED.value, "Resigned"),
        ]
    )


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
