from datetime import datetime

from pydantic import BaseModel, NaiveDatetime, model_validator

from app.models.event import EventStatus
from app.schemas.tag import TagOut


def _parse_recurrence_jours(recurrence_jours: str) -> list[int]:
    """Parse a CSV-of-ISO-weekday-ints string, raising ValueError on any
    out-of-range (not 1-7) or duplicate value."""
    try:
        jours = [int(part) for part in recurrence_jours.split(",")]
    except ValueError:
        raise ValueError("recurrence_jours must be a comma-separated list of integers")
    if any(jour < 1 or jour > 7 for jour in jours):
        raise ValueError("recurrence_jours values must be between 1 and 7 (ISO weekday)")
    if len(set(jours)) != len(jours):
        raise ValueError("recurrence_jours must not contain duplicate values")
    return jours


def _validate_event_dates(
    date: datetime | None,
    date_fin: datetime | None,
    recurrence_jours: str | None,
    recurrence_fin: datetime | None,
) -> None:
    """Shared cross-field validation for EventCreate/EventUpdate.

    Note: on EventUpdate, all fields are optional and independently settable
    via PATCH, so this only validates the combination *as submitted in this
    payload* — it cannot see a pre-existing stored `date` on partial updates
    (see events_backoffice.update_event for the separate cross-field check
    that covers that case).
    """
    if date_fin is not None and date is None:
        raise ValueError("date_fin cannot be set without date")

    if recurrence_jours is not None and date is None:
        raise ValueError("recurrence_jours cannot be set without date")

    jours: list[int] | None = None
    if recurrence_jours is not None:
        jours = _parse_recurrence_jours(recurrence_jours)

    if jours is not None:
        if date_fin is not None:
            if date is not None and date_fin.date() != date.date():
                raise ValueError(
                    "multi-day range and recurrence are mutually exclusive"
                )
    elif date_fin is not None and date is not None:
        if date_fin.date() < date.date():
            raise ValueError("date_fin must be on or after date")

    if recurrence_fin is not None and date is not None:
        if recurrence_fin.date() < date.date():
            raise ValueError("recurrence_fin must be on or after date")


class EventCreate(BaseModel):
    titre: str | None = None
    description: str | None = None
    source_url: str
    # NaiveDatetime (matches Event.date): rejects tz-aware input with a 422 at the
    # API boundary instead of silently accepting an offset that the Event table
    # model's own NaiveDatetime typing would not otherwise enforce (SQLModel table
    # models skip Pydantic validation on plain __init__/attribute assignment).
    date: NaiveDatetime | None = None
    # CSV of ISO weekday ints (1=Monday..7=Sunday), e.g. "1,4" = Tue+Fri.
    date_fin: NaiveDatetime | None = None
    recurrence_jours: str | None = None
    recurrence_fin: NaiveDatetime | None = None
    lieu: str | None = None
    image_url: str | None = None
    tag_ids: list[int] = []
    is_permanent: bool = False

    @model_validator(mode="after")
    def _validate_dates(self) -> "EventCreate":
        _validate_event_dates(self.date, self.date_fin, self.recurrence_jours, self.recurrence_fin)
        return self


class EventUpdate(BaseModel):
    titre: str | None = None
    description: str | None = None
    date: NaiveDatetime | None = None
    date_fin: NaiveDatetime | None = None
    recurrence_jours: str | None = None
    recurrence_fin: NaiveDatetime | None = None
    lieu: str | None = None
    image_url: str | None = None
    tag_ids: list[int] | None = None
    is_permanent: bool | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "EventUpdate":
        _validate_event_dates(self.date, self.date_fin, self.recurrence_jours, self.recurrence_fin)
        return self


class EventOut(BaseModel):
    id: int
    titre: str | None
    description: str | None
    source_url: str
    date: datetime | None
    date_fin: datetime | None
    recurrence_jours: str | None
    recurrence_fin: datetime | None
    lieu: str | None
    image_url: str | None
    statut: EventStatus
    created_by_id: int
    likes_count: int
    featured_editorial: bool
    is_permanent: bool
    tags: list[TagOut]


class EventCalendarOut(EventOut):
    """EventOut plus the resolved per-day occurrences for the queried month
    (see app/services/occurrences.py:occurrences_in_range). Only used by the
    `view=calendar` branch of GET /events.
    """

    occurrences: list[dict]
