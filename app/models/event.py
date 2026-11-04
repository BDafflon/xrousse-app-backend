from enum import Enum

from pydantic import NaiveDatetime
from sqlmodel import Field, Relationship, SQLModel

from app.models.tag import Tag


class EventStatus(str, Enum):
    brouillon = "brouillon"
    # Public event proposed by a user, waiting for an admin's decision.
    en_moderation = "en_moderation"
    # Public proposal rejected by an admin (see Event.motif_refus).
    refuse = "refuse"
    publie = "publie"


class EventVisibility(str, Enum):
    # Visible by its creator only. A private event never leaves `brouillon`,
    # so none of the public queries (which all filter statut == publie) can
    # ever expose it.
    prive = "prive"
    public = "public"


class EventTag(SQLModel, table=True):
    event_id: int | None = Field(
        default=None, foreign_key="event.id", primary_key=True
    )
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    titre: str | None = Field(default=None)
    description: str | None = Field(default=None)
    source_url: str = Field(unique=True, index=True)
    # NaiveDatetime intentionally REJECTS timezone-aware input (e.g. a client sending
    # "...+01:00" gets a 422), rather than silently normalizing/stripping the offset.
    # NOTE: this annotation alone only protects construction paths that run Pydantic
    # validation (e.g. `Event.model_validate(...)`); SQLModel table models do NOT
    # re-validate on plain `Event(date=...)` / attribute assignment, so the actual
    # enforcement point is `EventCreate.date` / `EventUpdate.date` in
    # app/schemas/event.py, which are also typed `NaiveDatetime` to reject aware
    # input at the API boundary before it ever reaches this model. If a future
    # frontend needs to send tz-aware ISO datetimes, either strip the offset
    # client-side before posting, or switch both this field and the schemas to
    # `datetime` and explicitly normalize (e.g. convert to UTC then drop tzinfo).
    date: NaiveDatetime | None = Field(default=None)
    date_fin: NaiveDatetime | None = Field(default=None)
    # CSV of ISO weekday ints (1=Mon..7=Sun), e.g. "2,5" = Tuesday + Friday.
    recurrence_jours: str | None = Field(default=None)
    recurrence_fin: NaiveDatetime | None = Field(default=None)
    lieu: str | None = Field(default=None)
    image_url: str | None = Field(default=None)
    statut: EventStatus = Field(default=EventStatus.brouillon)
    created_by_id: int = Field(foreign_key="user.id")
    likes_count: int = Field(default=0)
    # Number of public detail-page views (see POST /events/{id}/view). Only
    # exposed to admin/redacteur through BackofficeEventOut.
    views_count: int = Field(default=0)
    featured_editorial: bool = Field(default=False)
    is_permanent: bool = Field(default=False)
    visibilite: EventVisibility = Field(default=EventVisibility.public)
    motif_refus: str | None = Field(default=None)
    is_deleted: bool = Field(default=False)

    tags: list[Tag] = Relationship(link_model=EventTag)
