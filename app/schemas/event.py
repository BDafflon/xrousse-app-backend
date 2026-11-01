from datetime import datetime

from pydantic import BaseModel, NaiveDatetime, model_validator
from pydantic_core import InitErrorDetails, ValidationError

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


class EventDateError(ValueError):
    """Raised by `_validate_event_dates` for a specific offending field, so
    callers can report a precise `loc` (model_validators, which otherwise
    report errors at the whole-model/body level) or convert it into an
    HTTPException referencing that field (events_backoffice.update_event).
    """

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def _validate_event_dates(
    date: datetime | None,
    date_fin: datetime | None,
    recurrence_jours: str | None,
    recurrence_fin: datetime | None,
    *,
    require_date: bool = True,
) -> None:
    """Shared cross-field validation for EventCreate/EventUpdate, and reused
    by events_backoffice.update_event against the MERGED (post-setattr)
    event state so a PATCH to a single field can't create an invalid
    combination with the event's other already-stored fields.

    `require_date` gates the two standalone "X cannot be set without date"
    checks: they only make sense for EventCreate, where there is no prior
    stored state, so EventUpdate's own model_validator calls this with
    require_date=False and relies on events_backoffice.update_event's
    merged-state re-validation (which always runs with require_date=True)
    to catch the case where date is genuinely missing after the patch.
    """
    if require_date:
        if date_fin is not None and date is None:
            raise EventDateError("date_fin", "date_fin cannot be set without date")

        if recurrence_jours is not None and date is None:
            raise EventDateError(
                "recurrence_jours", "recurrence_jours cannot be set without date"
            )

    jours: list[int] | None = None
    if recurrence_jours is not None:
        try:
            jours = _parse_recurrence_jours(recurrence_jours)
        except ValueError as exc:
            raise EventDateError("recurrence_jours", str(exc)) from exc

    if jours is not None:
        if date_fin is not None:
            if date is not None and date_fin.date() != date.date():
                raise EventDateError(
                    "date_fin", "multi-day range and recurrence are mutually exclusive"
                )
    elif date_fin is not None and date is not None:
        if date_fin.date() < date.date():
            raise EventDateError("date_fin", "date_fin must be on or after date")

    if recurrence_fin is not None and date is not None:
        if recurrence_fin.date() < date.date():
            raise EventDateError(
                "recurrence_fin", "recurrence_fin must be on or after date"
            )


def _raise_as_field_error(model_name: str, exc: EventDateError) -> None:
    """Re-raise an EventDateError as a pydantic ValidationError whose `loc`
    ends in exc.field, instead of the whole-model loc that
    model_validator(mode="after") would otherwise produce for a plain
    ValueError. This is what lets the frontend's extractFieldErrors (which
    reads loc[-1]) highlight the right field.
    """
    raise ValidationError.from_exception_data(
        model_name,
        [
            InitErrorDetails(
                type="value_error",
                loc=(exc.field,),
                input=None,
                ctx={"error": ValueError(str(exc))},
            )
        ],
    ) from exc


class EventCreate(BaseModel):
    titre: str | None = None
    description: str | None = None
    source_url: str
    # NaiveDatetime (matches Event.date): rejects tz-aware input with a 422 at the
    # API boundary instead of silently accepting an offset that the Event table
    # model's own NaiveDatetime typing would not otherwise enforce (SQLModel table
    # models skip Pydantic validation on plain __init__/attribute assignment).
    date: NaiveDatetime | None = None
    date_fin: NaiveDatetime | None = None
    # CSV of ISO weekday ints (1=Monday..7=Sunday), e.g. "2,5" = Tue+Fri.
    recurrence_jours: str | None = None
    recurrence_fin: NaiveDatetime | None = None
    lieu: str | None = None
    image_url: str | None = None
    tag_ids: list[int] = []
    is_permanent: bool = False

    @model_validator(mode="after")
    def _validate_dates(self) -> "EventCreate":
        try:
            _validate_event_dates(
                self.date,
                self.date_fin,
                self.recurrence_jours,
                self.recurrence_fin,
                require_date=True,
            )
        except EventDateError as exc:
            _raise_as_field_error("EventCreate", exc)
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
        # require_date=False: on a PATCH, all fields are optional and
        # independently settable, so this only validates the combination
        # *as submitted in this payload* (e.g. a payload setting both `date`
        # and `date_fin` together, or both `date` and `recurrence_jours`
        # together, is still checked against itself here) — it cannot see a
        # pre-existing stored `date` on a partial update, so the standalone
        # "X cannot be set without date" checks are skipped (they'd
        # otherwise wrongly reject e.g. `PATCH {"date_fin": ...}` on an
        # event that already has a stored `date`). The merged-state check
        # that catches an invalid combination with the event's other
        # already-stored fields lives in
        # events_backoffice.update_event, which re-validates after applying
        # the payload to the actual stored event.
        try:
            _validate_event_dates(
                self.date,
                self.date_fin,
                self.recurrence_jours,
                self.recurrence_fin,
                require_date=False,
            )
        except EventDateError as exc:
            _raise_as_field_error("EventUpdate", exc)
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
