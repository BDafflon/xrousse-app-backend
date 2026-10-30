from datetime import datetime

from pydantic import BaseModel, NaiveDatetime

from app.models.event import EventStatus
from app.schemas.tag import TagOut


class EventCreate(BaseModel):
    titre: str | None = None
    description: str | None = None
    source_url: str
    # NaiveDatetime (matches Event.date): rejects tz-aware input with a 422 at the
    # API boundary instead of silently accepting an offset that the Event table
    # model's own NaiveDatetime typing would not otherwise enforce (SQLModel table
    # models skip Pydantic validation on plain __init__/attribute assignment).
    date: NaiveDatetime | None = None
    lieu: str | None = None
    image_url: str | None = None
    tag_ids: list[int] = []


class EventUpdate(BaseModel):
    titre: str | None = None
    description: str | None = None
    date: NaiveDatetime | None = None
    lieu: str | None = None
    image_url: str | None = None
    tag_ids: list[int] | None = None


class EventOut(BaseModel):
    id: int
    titre: str | None
    description: str | None
    source_url: str
    date: datetime | None
    lieu: str | None
    image_url: str | None
    statut: EventStatus
    created_by_id: int
    likes_count: int
    featured_editorial: bool
    tags: list[TagOut]
