"""Django ORM-backed implementation of `HolidayRepository`."""
from __future__ import annotations

from datetime import date

from apps.attendance.domain.entities import Holiday
from apps.attendance.domain.repositories import HolidayRepository
from apps.attendance.infrastructure.models import HolidayRecord
from shared_kernel.infrastructure.base_repository import DjangoBaseRepository


def _to_domain(record: HolidayRecord) -> Holiday:
    return Holiday(
        id=record.id,
        name=record.name,
        holiday_date=record.holiday_date,
        description=record.description,
        is_active=record.is_active,
    )


class DjangoHolidayRepository(DjangoBaseRepository[HolidayRecord, Holiday], HolidayRepository):
    model = HolidayRecord

    def _to_entity(self, record: HolidayRecord) -> Holiday:
        return _to_domain(record)

    def _to_record_kwargs(self, entity: Holiday) -> dict[str, object]:
        return {
            "name": entity.name,
            "holiday_date": entity.holiday_date,
            "description": entity.description,
            "is_active": entity.is_active,
        }

    def exists_with_date(self, holiday_date: date) -> bool:
        return self.model.objects.filter(holiday_date=holiday_date).exists()

    def get_dates_in_range(self, *, start_date: date, end_date: date) -> frozenset[date]:
        return frozenset(
            self.model.objects.filter(
                is_active=True, holiday_date__gte=start_date, holiday_date__lte=end_date
            ).values_list("holiday_date", flat=True)
        )

    def list_upcoming(self, *, from_date: date, limit: int) -> list[Holiday]:
        records = self.model.objects.filter(is_active=True, holiday_date__gte=from_date).order_by(
            "holiday_date"
        )[:limit]
        return [self._to_entity(r) for r in records]
