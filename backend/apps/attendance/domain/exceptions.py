"""Domain/application exceptions for Attendance."""
from __future__ import annotations

from shared_kernel.api.exceptions import ConflictError, NotFoundError


class HolidayNotFoundError(NotFoundError):
    """No holiday was found matching the given identifier."""

    code = "holiday_not_found"


class DuplicateHolidayDateError(ConflictError):
    """A holiday is already defined for this date."""

    code = "duplicate_holiday_date"


class HolidayReferencedByLeaveRequestError(ConflictError):
    """This holiday cannot be edited or deactivated because it is referenced by a recorded or approved leave request. Cancel the related leave request(s) first."""

    code = "holiday_referenced_by_leave_request"
