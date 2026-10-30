from enum import Enum

from pydantic import NaiveDatetime
from sqlmodel import Field, Relationship, SQLModel

from app.models.tag import Tag


class EventStatus(str, Enum):
    brouillon = "brouillon"
    publie = "publie"


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
    date: NaiveDatetime | None = Field(default=None)
    lieu: str | None = Field(default=None)
    image_url: str | None = Field(default=None)
    statut: EventStatus = Field(default=EventStatus.brouillon)
    created_by_id: int = Field(foreign_key="user.id")
    likes_count: int = Field(default=0)
    featured_editorial: bool = Field(default=False)

    tags: list[Tag] = Relationship(link_model=EventTag)
