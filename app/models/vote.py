from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


class Vote(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_vote_event_user"),
        UniqueConstraint("event_id", "anon_id", name="uq_vote_event_anon"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="event.id")
    user_id: int | None = Field(default=None, foreign_key="user.id")
    anon_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
