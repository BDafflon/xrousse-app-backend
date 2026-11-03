from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


class SavedEvent(SQLModel, table=True):
    """An event a logged-in user bookmarked ("Mes événements")."""

    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_saved_event_user_event"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    event_id: int = Field(foreign_key="event.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
